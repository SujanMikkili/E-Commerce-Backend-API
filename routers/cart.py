from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated,Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.testing import db
from starlette import status
from models import Products,CartItems,Cart,Users
from database import SessionLocal
from .auth import get_current_user,check_shopping_access
from passlib.context import CryptContext
from datetime import datetime

router = APIRouter(prefix="/cart",tags=["Cart"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency= Annotated[Session,Depends(get_db)]
user_dependency= Annotated[dict, Depends(get_current_user)]


@router.get("/",status_code=status.HTTP_200_OK)
async def get_cart(user:user_dependency,db:db_dependency):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if not current_user.customer_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Customer account is inactive")
    cart = db.query(Cart).filter(Cart.user_id == user["id"]).first()
    cart_items=db.query(CartItems).filter(CartItems.cart_id==cart.id).all()
    return cart_items

@router.post("/items",status_code=status.HTTP_201_CREATED)
async def add_product_to_cart(user:user_dependency,db:db_dependency,product_id:str,quantity:int):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if not current_user.customer_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,detail="Customer account is inactive")
    cart=db.query(Cart).filter(Cart.user_id==user["id"]).first()
    product=db.query(Products).filter(Products.id==product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found")
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Quantity must be greater than 0")
    if product.stock_quantity<quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Not enough stock available right now")
    cart_item=db.query(CartItems).filter(CartItems.cart_id==cart.id,
                                         CartItems.product_id==product_id).first()
    if cart_item:
        new_quantity=cart_item.quantity+quantity
        if product.stock_quantity<new_quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Not enough stock available")
        cart_item.quantity=new_quantity
    else:
        cart_item=CartItems(cart_id=cart.id,product_id=product_id,quantity=quantity)
        db.add(cart_item)
    cart.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cart_item)
    return cart_item


@router.put("/items/{item_id}",status_code=status.HTTP_200_OK)
async def update_cart_item(item_id: int,quantity: int,user: user_dependency,db: db_dependency):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if not current_user.customer_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Customer account is inactive")
    cart = db.query(Cart).filter(Cart.user_id == user["id"]).first()
    cart_item = db.query(CartItems).filter(CartItems.id == item_id,CartItems.cart_id == cart.id).first()
    if cart_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Cart item not found")
    if quantity < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Quantity cannot be negative")
    if quantity == 0:
        db.delete(cart_item)
        db.commit()
        return {"message": "Product removed from cart"}
    product = db.query(Products).filter(Products.id == cart_item.product_id).first()
    if product.stock_quantity < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Not enough stock available")
    cart_item.quantity = quantity
    cart.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cart_item)
    return cart_item


@router.delete("/items/{item_id}",status_code=status.HTTP_200_OK)
async def delete_item_from_cart(user:user_dependency,db:db_dependency,item_id:int):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if not current_user.customer_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Customer account is inactive")
    cart=db.query(Cart).filter(Cart.user_id==user["id"]).first()
    cart_item=db.query(CartItems).filter(CartItems.id==item_id,
                                         CartItems.cart_id==cart.id).first()
    if cart_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Cart item not found")
    db.delete(cart_item)
    cart.updated_at = datetime.utcnow()
    db.commit()
    return {"message":"Item removed from cart successfully"}
