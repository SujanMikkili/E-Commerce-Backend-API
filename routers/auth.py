from datetime import timedelta,timezone,datetime
from typing import Annotated
from jose import jwt,JWTError
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from starlette import status
from database import SessionLocal
from models import Users,Admins
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm,OAuth2PasswordBearer
from dotenv import load_dotenv
import os

load_dotenv()


router = APIRouter(prefix="/auth",tags=["Authentication"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/token")

class Token(BaseModel):
    access_token: str
    token_type: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency= Annotated[Session, Depends(get_db)]

def authenticate_user(username,password,db):
    user = db.query(Users).filter(Users.username == username).first()
    if user:
        if not user.is_active:
            return False
        if not bcrypt_context.verify(password, user.hashed_password):
            return False
        return user
    admin = db.query(Admins).filter(Admins.username == username).first()
    if admin:
        if not admin.is_active:
            return False
        if not bcrypt_context.verify(password, admin.hashed_password):
            return False
        return admin
    return False


def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode={'sub': username,'id': user_id,'role': role}
    expires=datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        user_role:str =payload.get('role')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Could not validate user.")
        return {'username':username,'id':user_id,'user_role':user_role}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Could not validate user.")

def check_shopping_access(user):
    if user["user_role"] not in ("Customer", "Seller"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admins are not allowed to use shopping features.")


def check_seller_access(user):
    if user["user_role"] != "Seller":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Seller access required")


@router.post("/token",response_model=Token)
async def login_for_access_token(form_data:Annotated[OAuth2PasswordRequestForm, Depends()],db:db_dependency):
    user = authenticate_user(form_data.username, form_data.password,db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Could not validate user.")
    if isinstance(user, Admins):
        role = "Admin"
    else:
        role = user.role
    token=create_access_token(user.username,user.id,role,timedelta(minutes=20))
    return {'access_token':token,'token_type':'bearer'}
