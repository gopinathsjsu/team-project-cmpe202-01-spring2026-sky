import os
from fastapi import HTTPException, APIRouter
from pydantic import BaseModel, EmailStr
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

if not all([AWS_REGION, USER_POOL_ID, CLIENT_ID]):
    print("ENV DEBUG:")
    print("AWS_REGION:", AWS_REGION)
    print("USER_POOL_ID:", USER_POOL_ID)
    print("CLIENT_ID:", CLIENT_ID)
    raise Exception("Missing required environment variables.")

cognito = boto3.client("cognito-idp", region_name=AWS_REGION)
router = APIRouter(prefix="/auth", tags=["authentication"])

class SignUpRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class ConfirmRequest(BaseModel):
    email: EmailStr
    code: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    access_token: str


@router.post("/signup")
def signup(data: SignUpRequest):
    try:
        response = cognito.sign_up(
            ClientId=CLIENT_ID,
            Username=data.email,
            Password=data.password,
            UserAttributes=[
                {"Name": "email", "Value": data.email},
                {"Name": "name", "Value": data.name},
            ],
        )

        return {
            "message": "User created successfully",
            "statusCode": 200,
            "user_sub": response["UserSub"],
            "confirmation_required": not response["UserConfirmed"],
        }
    except ClientError as e:
        raise HTTPException(400, e.response["Error"]["Message"])

@router.post("/confirm")
def confirm_signup(data: ConfirmRequest):
    try:
        cognito.confirm_sign_up(
            ClientId=CLIENT_ID,
            Username=data.email,
            ConfirmationCode=data.code,
        )
        return {"message": "User confirmed successfully", "statusCode": 200}
    except ClientError as e:
        raise HTTPException(400, e.response["Error"]["Message"])

@router.post("/login")
def login(data: LoginRequest):
    try:
        response = cognito.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": data.email,
                "PASSWORD": data.password,
            },
        )

        return response["AuthenticationResult"]
    except cognito.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except cognito.exceptions.UserNotConfirmedException:
        raise HTTPException(status_code=403, detail="User not confirmed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def refresh_token(data: RefreshRequest):
    try:
        response = cognito.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={
                "REFRESH_TOKEN": data.refresh_token,
            },
        )

        return response["AuthenticationResult"]

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.post("/logout")
def logout_user(data: LogoutRequest):
    try:
        cognito.global_sign_out(
            AccessToken=data.access_token,
        )
        return {"message": "User logged out successfully", "statusCode": 200}
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in {"NotAuthorizedException", "InvalidParameterException"}:
            raise HTTPException(status_code=401, detail="Invalid or expired access token")
        raise HTTPException(status_code=400, detail=e.response["Error"]["Message"])
