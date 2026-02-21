"""
AWS Secrets Manager integration utilities
"""
import boto3
from functools import lru_cache
from typing import Dict


@lru_cache(maxsize=None)
def get_secret(secret_name: str, region: str = "ap-northeast-1") -> str:
    """
    Retrieve secret from AWS Secrets Manager (with caching)

    Args:
        secret_name: Secret name (e.g., izakaya-agent/hotpepper-api-key)
        region: AWS region

    Returns:
        Secret value as string
    """
    client = boto3.client('secretsmanager', region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']


def get_api_keys() -> Dict[str, str]:
    """
    Retrieve all API keys in bulk

    Returns:
        Dictionary of API keys
    """
    return {
        "hotpepper": get_secret("izakaya-agent/hotpepper-api-key"),
        "google_places": get_secret("izakaya-agent/google-places-api-key"),
        "line_channel_secret": get_secret("izakaya-agent/line-channel-secret"),
        "line_access_token": get_secret("izakaya-agent/line-channel-access-token"),
    }


def validate_secrets() -> None:
    """
    Validate that required secrets are set in AWS Secrets Manager.

    This function checks that all required API keys are configured and non-empty.
    It should be called at agent startup to fail fast if secrets are missing.

    Raises:
        ValueError: If any required secret is not set or empty
    """
    required_secrets = [
        "izakaya-agent/hotpepper-api-key",
        "izakaya-agent/google-places-api-key",
    ]

    for secret_name in required_secrets:
        try:
            value = get_secret(secret_name)
            if not value or value.strip() == "":
                raise ValueError(
                    f"Secret '{secret_name}' is empty. "
                    f"Please configure it in AWS Secrets Manager using:\n"
                    f"aws secretsmanager put-secret-value --secret-id {secret_name} "
                    f"--secret-string \"YOUR_API_KEY\" --region ap-northeast-1"
                )
        except Exception as e:
            if "ResourceNotFoundException" in str(e):
                raise ValueError(
                    f"Secret '{secret_name}' does not exist. "
                    f"Please create it first using CDK deployment."
                ) from e
            raise
