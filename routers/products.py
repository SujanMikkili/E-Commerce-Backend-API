from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette import status
from models import Products, Sellers
from database import SessionLocal
from .auth import get_current_user,check_shopping_access,check_seller_access
from passlib.context import CryptContext


router = APIRouter(prefix="/products",tags=["Products"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


bcrypt_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

class ProductRequest(BaseModel):
    name: str
    category: str
    description: str
    price: float = Field(gt=0)
    stock_quantity: int = Field(ge=0)


class UserVerification(BaseModel):
    password: str
    new_password: str = Field(min_length=6)


@router.get("/", status_code=status.HTTP_200_OK)
async def get_products(db: db_dependency,user:user_dependency):
    check_shopping_access(user)
    products = db.query(Products).filter(Products.approval_status == "Approved").all()
    return products



@router.put("/my-products/{product_number}",status_code=status.HTTP_200_OK)
async def update_product(user: user_dependency,db: db_dependency,product_number: int,
                         name: Optional[str] = None,category: Optional[str] = None,
                         description: Optional[str] = None,price: Optional[float] = None,
                         stock_quantity: Optional[int] = None):
    check_seller_access(user)
    seller = db.query(Sellers).filter(Sellers.user_id == user["id"]).first()
    if seller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Only sellers can update products")
    product = db.query(Products).filter(Products.id == product_number,
                                        Products.seller_id == seller.id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found")
    if name is not None:
        product.name = name
    if category is not None:
        product.category = category
    if description is not None:
        product.description = description
    if price is not None:
        product.price = price
    if stock_quantity is not None:
        product.stock_quantity = stock_quantity
    product.approval_status = "Pending"
    product.rejection_reason = None
    db.commit()
    db.refresh(product)
    return {"product_id": product.id,
            "product": product}


@router.get("/my-products",status_code=status.HTTP_200_OK)
async def get_my_products(user: user_dependency,db: db_dependency):
    check_seller_access(user)
    seller = db.query(Sellers).filter(Sellers.user_id == user["id"]).first()
    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,detail="Only sellers can view products")
    products = db.query(Products).filter(Products.seller_id == seller.id).all()
    result = []
    for product in products:
        result.append({"product_id": product.id,
                       "name": product.name,
                       "category": product.category,
                       "description": product.description,
                       "price": product.price,
                       "stock_quantity": product.stock_quantity,
                       "approval_status": product.approval_status,
                       "rejection_reason": product.rejection_reason})
    return result




@router.get("/{product_id}",status_code=status.HTTP_200_OK)
async def get_products_by_id(product_id: int,db: db_dependency,user: user_dependency):
    check_shopping_access(user)
    product = db.query(Products).filter(Products.id == product_id,
                                        Products.approval_status == "Approved").first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found")
    return product


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_product(user: user_dependency,db: db_dependency,name: str,
                         category: str,description: str,price: float,
                         stock_quantity: int):
    check_seller_access(user)
    seller = db.query(Sellers).filter(Sellers.user_id == user["id"]).first()
    if seller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Only Sellers can add product")
    new_product = Products(seller_id=seller.id,name=name,category=category,
                           description=description,price=price,
                           stock_quantity=stock_quantity,approval_status="Pending")
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@router.delete("/{product_number}",status_code=status.HTTP_200_OK)
async def delete_product(product_number: int,user: user_dependency,db: db_dependency):
    check_seller_access(user)
    seller = db.query(Sellers).filter(Sellers.user_id == user["id"]).first()
    if seller is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Only sellers can delete products")
    product = db.query(Products).filter(Products.id == product_number,
                                        Products.seller_id == seller.id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}
