import os

import boto3
from fastapi import HTTPException


def get_aws_region() -> str:
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region:
        raise HTTPException(status_code=500, detail="AWS region is not configured")
    return region


def get_user_pool_id() -> str:
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID") or os.getenv("USER_POOL_ID")
    if not user_pool_id:
        raise HTTPException(status_code=500, detail="COGNITO_USER_POOL_ID is not configured")
    return user_pool_id


def get_cognito_client():
    return boto3.client("cognito-idp", region_name=get_aws_region())
