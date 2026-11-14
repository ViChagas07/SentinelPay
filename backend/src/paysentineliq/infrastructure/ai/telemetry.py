import os


def configure_ai_telemetry() -> None:
    env = {
        "OTEL_SDK_DISABLED": "true",
        "CREWAI_DISABLE_TELEMETRY": "true",
        "CREWAI_DISABLE_TRACKING": "true",
        "CREWAI_TRACING_ENABLED": "false",
        "LANGCHAIN_TRACING_V2": "false",
        "LANGCHAIN_TRACING": "false",
        "LANGSMITH_TRACING": "false",
        "ANONYMIZED_TELEMETRY": "false",
    }
    for key, value in env.items():
        os.environ[key] = value
