from fastmcp import Client

from capability_bridge.core.capabilities.vision import VisionCapability
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.routing.policy import RoutingPolicy
from capability_bridge.transports.mcp.server import create_server
from helpers import FakeProvider, make_image


def _server() -> object:
    policy = RoutingPolicy([FakeProvider("qwen")], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})
    return create_server(capability)


async def test_tools_exposed() -> None:
    async with Client(_server()) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert {"vision_analyze", "vision_ocr"} <= names


async def test_vision_analyze_call(tmp_path) -> None:
    async with Client(_server()) as client:
        result = await client.call_tool(
            "vision_analyze", {"image": make_image(tmp_path), "prompt": "describe this"}
        )
        assert "result-from-qwen" in str(result.content)


async def test_prompt_passes_through_mcp_to_provider_unchanged(tmp_path) -> None:
    """Checkpoint 3: full-chain fidelity — MCP tool -> VisionCapability -> RoutingPolicy ->
    FakeProvider.last_request.prompt must be byte-identical to what the tool was given."""
    provider = FakeProvider("qwen")
    policy = RoutingPolicy([provider], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})
    prompt = "Analyze hierarchy, spacing, typography, and color as a senior product designer."
    async with Client(create_server(capability)) as client:
        await client.call_tool("vision_analyze", {"image": make_image(tmp_path), "prompt": prompt})
    assert provider.last_request is not None
    assert provider.last_request.prompt == prompt
