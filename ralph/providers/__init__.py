from ralph.providers.base import BaseProvider
from ralph.providers.claude_sdk import ClaudeSDKProvider
from ralph.providers.deep_agents import DeepAgentsProvider

PROVIDERS = {
    "claude-sdk": ClaudeSDKProvider,
    "deep-agents": DeepAgentsProvider,
}


def create_provider(name: str, **kwargs) -> BaseProvider:
    """Factory to create a provider by name."""
    if name not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{name}'. Choose from: {available}")
    return PROVIDERS[name](**kwargs)
