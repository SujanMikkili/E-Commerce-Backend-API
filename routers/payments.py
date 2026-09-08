from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from datetime import datetime
import uuid
from models import Orders,Payments,Products,OrderItems,Cart,CartItems
from database import SessionLocal
from .auth import get_current_user,check_shopping_access


router = APIRouter(prefix="/payments",tags=["Payments"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


class PaymentRequest(BaseModel):
    payment_method: str
    simulate_failure: bool = False


@router.post("/{order_number}/pay",status_code=status.HTTP_200_OK)
async def pay_for_order(order_number: int,payment_request: PaymentRequest,
                        user: user_dependency,db: db_dependency):
    check_shopping_access(user)
    order = db.query(Orders).filter(Orders.id == order_number,Orders.user_id == user["id"]).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Order not found")
    if order.status not in ("Awaiting Payment","Payment Failed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Order is '{order.status}' and cannot be paid for")
    payment = db.query(Payments).filter(Payments.order_id == order.id).first()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Payment record not found")
    if payment.payment_status == "Success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Order has already been paid for")
    if payment.payment_method == "COD":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cash on Delivery orders do not require online payment")
    requested_payment_method = payment_request.payment_method.strip().upper()
    if requested_payment_method not in ("UPI", "CARD"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid payment method. Use UPI or CARD")
    if requested_payment_method != payment.payment_method:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"This order was created using {payment.payment_method}")
    order_items = db.query(OrderItems).filter(OrderItems.order_id == order.id).all()
    if not order_items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No items found for this order")
    if order.status == "Payment Failed":
        for order_item in order_items:
            if order_item.status == "Cancelled":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Cancelled items cannot be paid for again")
            product = db.query(Products).filter(Products.id == order_item.product_id).first()
            if product is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Product {order_item.product_id} not found")
            if product.approval_status != "Approved":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Product {product.id} is no longer available")
            if product.stock_quantity < order_item.quantity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Not enough stock for product {product.id}")
        for order_item in order_items:
            product = db.query(Products).filter(Products.id == order_item.product_id).first()
            product.stock_quantity -= order_item.quantity
            product.reserved_quantity += order_item.quantity
        order.status = "Awaiting Payment"
    if payment_request.simulate_failure:
        cart = db.query(Cart).filter(Cart.user_id == user["id"]).first()
        if cart is None:
            cart = Cart(user_id=user["id"])
            db.add(cart)
            db.flush()
        for order_item in order_items:
            product = db.query(Products).filter(Products.id == order_item.product_id).first()
            if product is not None:
                if product.reserved_quantity >= order_item.quantity:
                    product.reserved_quantity -= order_item.quantity
                    product.stock_quantity += order_item.quantity
            cart_item = db.query(CartItems).filter(CartItems.cart_id == cart.id,
                                                   CartItems.product_id == order_item.product_id).first()
            if cart_item is None:
                cart_item = CartItems(cart_id=cart.id,
                                      product_id=order_item.product_id,
                                      quantity=order_item.quantity)
                db.add(cart_item)
            else:
                cart_item.quantity += order_item.quantity
        cart.updated_at = datetime.utcnow()
        payment.payment_status = "Failed"
        order.status = "Payment Failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment failed. Products have been returned to stock and added back to your cart."
        )
    for order_item in order_items:
        product = db.query(Products).filter(Products.id == order_item.product_id).first()
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Product {order_item.product_id} not found")
        if product.reserved_quantity < order_item.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Reserved stock not found for product {product.id}")
    cart = db.query(Cart).filter(Cart.user_id == user["id"]).first()
    if cart is not None:
        for order_item in order_items:
            cart_item = db.query(CartItems).filter(CartItems.cart_id == cart.id,
                                                   CartItems.product_id == order_item.product_id).first()
            if cart_item is not None:
                if cart_item.quantity <= order_item.quantity:
                    db.delete(cart_item)
                else:
                    cart_item.quantity -= order_item.quantity
        cart.updated_at = datetime.utcnow()
    for order_item in order_items:
        product = db.query(Products).filter(Products.id == order_item.product_id).first()
        product.reserved_quantity -= order_item.quantity
    payment.payment_method = requested_payment_method
    payment.payment_status = "Success"
    payment.transaction_id = str(uuid.uuid4())
    payment.paid_at = datetime.utcnow()
    order.status = "Paid"
    db.commit()
    db.refresh(payment)
    db.refresh(order)
    return {"message": "Payment successful",
            "order_number": order.id,
            "order_id": order.id,
            "payment_id": payment.id,
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "payment_status": payment.payment_status,
            "transaction_id": payment.transaction_id,
            "paid_at": payment.paid_at,
            "order_status": order.status}


@router.get("/{order_number}",status_code=status.HTTP_200_OK)
async def get_payment_status(order_number: int,user: user_dependency,db: db_dependency):
    check_shopping_access(user)
    order = db.query(Orders).filter(Orders.id == order_number,Orders.user_id == user["id"]).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Order not found")
    payment = db.query(Payments).filter(Payments.order_id == order.id).first()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Payment not found for this order")
    return {"order_number": order.id,
            "order_id": order.id,
            "payment_id": payment.id,
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "payment_status": payment.payment_status,
            "transaction_id": payment.transaction_id,
            "paid_at": payment.paid_at,
            "refund_status": payment.refund_status,
            "refunded_amount": payment.refunded_amount,
            "refund_transaction_id": payment.refund_transaction_id,
            "refunded_at": payment.refunded_at}

