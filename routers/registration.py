from typing import Annotated
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from database import SessionLocal
from models import Users,Sellers,Cart
from passlib.context import CryptContext


router = APIRouter(prefix="/auth",tags=["Registration"])
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency= Annotated[Session, Depends(get_db)]

class CreateUserRequest(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str
    password: str
    phone_number: str

class SellerRegisterRequest(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str
    password: str
    phone_number: str
    store_name: str
    store_description: str


@router.post("/customer", status_code=status.HTTP_201_CREATED)
async def register_as_customer(db: db_dependency,username: str,
                               email: str,first_name: str,last_name: str,
                               password: str,phone_number: str):
    create_user_model = Users(username=username,email=email,
                              first_name=first_name,last_name=last_name,
                              hashed_password=bcrypt_context.hash(password),
                              phone_number=phone_number,is_active=True,
                              role="Customer")
    db.add(create_user_model)
    db.commit()
    db.refresh(create_user_model)
    new_cart = Cart(user_id=create_user_model.id)
    db.add(new_cart)
    db.commit()
    return {"message": "Customer registered successfully"}


@router.post("/seller", status_code=status.HTTP_201_CREATED)
async def register_as_seller(db: db_dependency,username: str,email: str,
                             first_name: str,last_name: str,password: str,
                             phone_number: str,store_name: str,store_description: str):
    create_user_model = Users(username=username,email=email,first_name=first_name,
                              last_name=last_name,hashed_password=bcrypt_context.hash(password),
                              phone_number=phone_number,is_active=True,role="Seller")
    db.add(create_user_model)
    db.commit()
    db.refresh(create_user_model)
    create_seller_model = Sellers(user_id=create_user_model.id,store_name=store_name,
                                  store_description=store_description,is_active=True)
    db.add(create_seller_model)
    db.commit()
    db.refresh(create_seller_model)
    new_cart = Cart(user_id=create_user_model.id)
    db.add(new_cart)
    db.commit()
    return {"message": "Seller registered successfully"}
