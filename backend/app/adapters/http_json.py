"""HTTP JSON bridge adapter for operator-configured voice-agent runtimes."""

from __future__ import annotations

import ipaddress
import os
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.scenarios import AgentObservation, EvidenceMode, Scenario


class BridgeResponse(BaseModel):
    """Strict response envelope emitted by the voice-agent bridge endpoint."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal[1]
    status: Literal["completed"]
    transcript: str = Field(default="", max_length=100_000)
    latency_ms: float | None = Field(default=None, ge=0)
    tools_called: list[str] = Field(default_factory=list, max_length=100)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)


class HTTPJSONAgentAdapter:
    """Call a configured server-side Pixi bridge endpoint.

    This is a transport contract, not a built-in integration with any named vendor. The
    configured endpoint must execute the scenario and return the versioned bridge schema.
    The browser never supplies the URL or the credential. Redirects are not followed.
    """

    name = "http-json-bridge"
    evidence_mode = EvidenceMode.LIVE

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_insecure_localhost: bool = False,
    ) -> None:
        self.endpoint = self._validate_endpoint(
            endpoint, allow_insecure_localhost=allow_insecure_localhost
        )
        if not 0.1 <= timeout_seconds <= 30:
            raise ValueError("Agent bridge timeout must be between 0.1 and 30 seconds.")
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self._transport = transport

    @staticmethod
    def _validate_endpoint(endpoint: str, *, allow_insecure_localhost: bool) -> str:
        value = endpoint.strip()
        parsed = urlparse(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("Agent bridge endpoint must be an absolute HTTP(S) URL.")
        is_loopback = parsed.hostname.lower() == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            pass
        if parsed.scheme != "https" and not (allow_insecure_localhost and is_loopback):
            raise ValueError("Agent bridge endpoints must use HTTPS except local development loopback.")
        return value

    async def execute(self, scenario: Scenario) -> AgentObservation:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "protocol_version": 1,
            "scenario": scenario.model_dump(mode="json"),
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            try:
                response = await client.post(self.endpoint, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise RuntimeError("Agent bridge request timed out.") from exc
            except httpx.HTTPError as exc:
                raise RuntimeError("Agent bridge request failed before a response was received.") from exc

        if response.is_redirect:
            raise RuntimeError("Agent bridge redirects are disabled; use the final HTTPS endpoint.")
        if response.is_error:
            raise RuntimeError(f"Agent bridge returned HTTP {response.status_code}.")
        try:
            body = response.json()
            envelope = BridgeResponse.model_validate(body)
        except (ValueError, ValidationError) as exc:
            raise RuntimeError("Agent bridge response did not match protocol version 1.") from exc

        # The remote payload cannot claim that it is live or simulated. Provenance is
        # assigned here because the response came through the configured external bridge.
        return AgentObservation(
            transcript=envelope.transcript,
            latency_ms=envelope.latency_ms,
            tools_called=envelope.tools_called,
            error=None,
            evidence_mode=EvidenceMode.LIVE,
            provider=envelope.provider or "configured-http-bridge",
            model=envelope.model,
        )


def build_configured_http_adapter() -> HTTPJSONAgentAdapter:
    """Construct a bounded adapter from server-side environment variables."""
    endpoint = os.getenv("PIXI_AGENT_ENDPOINT", "").strip()
    if not endpoint:
        raise ValueError("PIXI_AGENT_ENDPOINT is not configured.")
    timeout_text = os.getenv("PIXI_AGENT_TIMEOUT_SECONDS", "15")
    try:
        timeout = float(timeout_text)
    except ValueError as exc:
        raise ValueError("PIXI_AGENT_TIMEOUT_SECONDS must be a number from 0.1 to 30.") from exc
    return HTTPJSONAgentAdapter(
        endpoint=endpoint,
        api_key=os.getenv("PIXI_AGENT_API_KEY") or None,
        timeout_seconds=timeout,
        allow_insecure_localhost=os.getenv("APP_ENV", "production").lower() == "development",
    )
