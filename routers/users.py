from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated,Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette import status
from models import Users,Addresses,Cart,CartItems,Sellers
from database import SessionLocal
from .auth import get_current_user,check_shopping_access
from passlib.context import CryptContext


router = APIRouter(
    prefix="/users",tags=["Users"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency= Annotated[Session,Depends(get_db)]
user_dependency= Annotated[dict, Depends(get_current_user)]
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserVerification(BaseModel):
    password: str
    new_password: str = Field(min_length=6)

@router.get("/me",status_code=status.HTTP_200_OK)
async def user_info(user:user_dependency,db:db_dependency):
    check_shopping_access(user)
    current_user=db.query(Users).filter(Users.id==user["id"]).first()
    if current_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return current_user


@router.post("/address",status_code=status.HTTP_200_OK)
async def create_address(user:user_dependency,db:db_dependency,
                         door_no:str,street:str,area:str,city:str,
                         district:str,state:str,pincode:str,country:str):
    check_shopping_access(user)
    new_address=Addresses(user_id=user["id"],door_no=door_no,street=street,
                          area=area,city=city,district=district,state=state,
                          pincode=pincode,country=country)
    db.add(new_address)
    db.commit()
    db.refresh(new_address)
    return new_address

@router.get("/addresses", status_code=status.HTTP_200_OK)
async def get_addresses(user: user_dependency,db: db_dependency):
    check_shopping_access(user)
    addresses = db.query(Addresses).filter(Addresses.user_id == user["id"]).all()
    return addresses


@router.put("/address/{address_id}",status_code=status.HTTP_200_OK)
async def update_address( user:user_dependency,db:db_dependency,
                          address_number:int,door_no:Optional[str]=None,
                          street:Optional[str]=None,area:Optional[str]=None,
                          city:Optional[str]=None,district:Optional[str]=None,
                          state:Optional[str]=None,country:Optional[str]=None,
                          pincode:Optional[str]=None):
    check_shopping_access(user)
    addresses=db.query(Addresses).filter(Addresses.user_id==user["id"]).all()
    if address_number < 1 or address_number > len(addresses):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Address not found")
    address = addresses[address_number - 1]
    if address_number is None:
        raise HTTPException(status_code=404, detail="Address not found")
    if door_no is not None:
        address.door_no = door_no
    if street is not None:
        address.street = street
    if area is not None:
        address.area = area
    if city is not None:
        address.city = city
    if district is not None:
        address.district = district
    if state is not None:
        address.state = state
    if pincode is not None:
        address.pincode = pincode
    if country is not None:
        address.country = country
    db.commit()
    db.refresh(address)
    return address


@router.put("/me/phone_number",status_code=status.HTTP_200_OK)
async def update_phone_number(user:user_dependency,db:db_dependency,new_phone_number:str):
    check_shopping_access(user)
    number=db.query(Users).filter(Users.id==user["id"]).first()
    number.phone_number=new_phone_number
    db.commit()
    db.refresh(number)
    return number


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_user(user: user_dependency,db: db_dependency):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
    seller=db.query(Sellers).filter(Sellers.user_id==user["id"]).first()
    cart=db.query(Cart).filter(Cart.user_id==user["id"]).first()
    if cart:
        db.query(CartItems).filter(CartItems.cart_id==cart.id).delete()
        db.delete(cart)
    if seller:
        current_user.customer_active=False
    else:
        db.query(Addresses).filter(Addresses.user_id==user["id"]).delete()
        db.delete(current_user)
        db.commit()
        return {"message": "Customer account deleted successfully"}
