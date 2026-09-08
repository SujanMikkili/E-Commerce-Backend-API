from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, Optional
from sqlalchemy.orm import Session
from starlette import status
from database import SessionLocal
from models import Users,Cart,CartItems,Products,Orders,OrderItems,Addresses,Payments,ReturnRequests
from .auth import get_current_user,check_shopping_access
from datetime import datetime
import uuid


router = APIRouter(prefix="/orders",tags=["Orders"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]



@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order(user: user_dependency,db: db_dependency,address_number: int,payment_method: str):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
    if not current_user.customer_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Customer account is inactive")
    address = db.query(Addresses).filter(Addresses.id == address_number,Addresses.user_id == user["id"]).first()
    if address is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Address not found")
    cart = db.query(Cart).filter(Cart.user_id == user["id"]).first()
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Cart not found")
    cart_items = db.query(CartItems).filter(CartItems.cart_id == cart.id).all()
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Your cart is empty")
    payment_method = payment_method.strip().upper()
    if payment_method not in ("COD", "UPI", "CARD"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Invalid payment method. Use COD, UPI or CARD")
    total_amount = 0
    for item in cart_items:
        product = db.query(Products).filter(Products.id == item.product_id).first()
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"Product {item.product_id} not found")
        if product.approval_status != "Approved":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"Product {product.id} is not available")
        if product.stock_quantity < item.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"Not enough stock for product {product.id}")
        total_amount += product.price * item.quantity
    for item in cart_items:
        product = db.query(Products).filter(Products.id == item.product_id).first()
        product.stock_quantity -= item.quantity
        product.reserved_quantity += item.quantity
    new_order = Orders(user_id=user["id"],total_amount=total_amount,
                       status="Awaiting Payment",shipping_address_id=address.id)
    db.add(new_order)
    db.flush()

    for item in cart_items:
        product = db.query(Products).filter(Products.id == item.product_id).first()
        item_total = product.price * item.quantity
        order_item = OrderItems(order_id=new_order.id,product_id=item.product_id,
                                quantity=item.quantity,price=product.price,
                                total_price=item_total)
        db.add(order_item)
    new_payment = Payments(order_id=new_order.id,payment_method=payment_method,
                           amount=total_amount,payment_status="Pending")
    db.add(new_payment)
    for item in cart_items:
        db.delete(item)
    cart.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(new_order)
    db.refresh(new_payment)
    return {"message": "Order created. Complete payment to confirm it.",
            "order_id": new_order.id,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "payment_status": new_payment.payment_status,
            "status": new_order.status,
            "next_step": f"POST /payments/{new_order.id}/pay"}


@router.post("/buy-item/{item_number}",status_code=status.HTTP_201_CREATED)
async def buy_cart_item(user: user_dependency,db: db_dependency,item_number: int,
                        address_number: int,payment_method: str):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
    if not current_user.customer_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Customer account is inactive")
    address = db.query(Addresses).filter(Addresses.id == address_number,Addresses.user_id == user["id"]).first()
    if address is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Address not found")
    cart = db.query(Cart).filter(Cart.user_id == user["id"]).first()
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Cart not found")
    cart_item = db.query(CartItems).filter(CartItems.id == item_number,
                                           CartItems.cart_id == cart.id).first()
    if cart_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Cart item not found")
    product = db.query(Products).filter(Products.id == cart_item.product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Product not found")
    if product.approval_status != "Approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Product is not available")
    if product.stock_quantity < cart_item.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Not enough stock for product {product.id}")
    payment_method = payment_method.strip().upper()
    if payment_method not in ("COD", "UPI", "CARD"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid payment method. Use COD, UPI or CARD")
    total_amount = product.price * cart_item.quantity
    product.stock_quantity -= cart_item.quantity
    product.reserved_quantity += cart_item.quantity
    new_order = Orders(user_id=user["id"],total_amount=total_amount,
                       status="Awaiting Payment",shipping_address_id=address.id)
    db.add(new_order)
    db.flush()
    order_item = OrderItems(order_id=new_order.id,product_id=cart_item.product_id,
                            quantity=cart_item.quantity,price=product.price,
                            total_price=total_amount)
    db.add(order_item)
    new_payment = Payments(order_id=new_order.id,payment_method=payment_method,
                           amount=total_amount,payment_status="Pending")
    db.add(new_payment)
    db.delete(cart_item)
    cart.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(new_order)
    db.refresh(new_payment)
    return {"message": "Order created. Complete payment to confirm it.",
            "order_id": new_order.id,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "payment_status": new_payment.payment_status,
            "status": new_order.status,
            "next_step": f"POST /payments/{new_order.id}/pay"}


@router.get("/",status_code=status.HTTP_200_OK)
async def get_my_orders(user: user_dependency,db: db_dependency):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
    if not current_user.customer_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Customer account is inactive")
    orders = db.query(Orders).filter(Orders.user_id == user["id"]).all()
    result = []
    for order in orders:
        order_items = db.query(OrderItems).filter(OrderItems.order_id == order.id).all()
        result.append({"order_id": order.id,
                       "total_amount": order.total_amount,
                       "status": order.status,
                       "shipping_address_id": order.shipping_address_id,
                       "created_at": order.created_at,
                       "updated_at": order.updated_at,
                       "items": order_items})
    return result


@router.get("/{order_number}",status_code=status.HTTP_200_OK)
async def get_order(user: user_dependency,db: db_dependency,order_number: int):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="User not found")
    if not current_user.customer_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Customer account is inactive")
    order = db.query(Orders).filter(Orders.id == order_number,Orders.user_id == user["id"]).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Order not found")
    order_items = db.query(OrderItems).filter(OrderItems.order_id == order.id).all()
    return {"order_id": order.id,
            "total_amount": order.total_amount,
            "status": order.status,
            "shipping_address_id": order.shipping_address_id,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": order_items}


@router.put("/{order_number}/cancel", status_code=status.HTTP_200_OK)
async def cancel_order(user: user_dependency,db: db_dependency,
                       order_number: int,item_number: Optional[int] = None):
    check_shopping_access(user)
    current_user = db.query(Users).filter(Users.id == user["id"]).first()
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found")
    if not current_user.customer_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Customer account is inactive")
    order = db.query(Orders).filter(Orders.id == order_number,
                                    Orders.user_id == user["id"]).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Order not found")
    if order.status not in ("Awaiting Payment","Payment Failed","Paid","Processing"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Order in status '{order.status}' cannot be cancelled")
    payment = db.query(Payments).filter(Payments.order_id == order.id).first()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Payment record not found")
    if item_number is not None:
        order_item = db.query(OrderItems).filter(OrderItems.id == item_number,
                                                 OrderItems.order_id == order.id).first()
        if order_item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Order item not found")
        if order_item.status == "Cancelled":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Item is already cancelled")
        product = db.query(Products).filter(Products.id == order_item.product_id).first()
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Product not found")
        if order.status == "Awaiting Payment":
            if product.reserved_quantity >= order_item.quantity:
                product.reserved_quantity -= order_item.quantity
                product.stock_quantity += order_item.quantity
        elif order.status in ("Paid", "Processing"):
            product.stock_quantity += order_item.quantity
        order_item.status = "Cancelled"
        refund_amount = order_item.total_price
        order.total_amount -= refund_amount
        if payment.payment_method == "COD":
            actual_refund = 0
            if order.total_amount == 0:
                payment.payment_status = "Cancelled"
        else:
            if payment.payment_status == "Success":
                payment.refund_status = "Refunded"
                if payment.refunded_amount is None:
                    payment.refunded_amount = refund_amount
                else:
                    payment.refunded_amount += refund_amount
                payment.refund_transaction_id = str(uuid.uuid4())
                payment.refunded_at = datetime.utcnow()
                actual_refund = refund_amount
            else:
                payment.payment_status = "Cancelled"
                actual_refund = 0
        remaining_item = db.query(OrderItems).filter(OrderItems.order_id == order.id,
                                                     OrderItems.status != "Cancelled").first()
        if remaining_item is None:
            order.status = "Cancelled"
            order.total_amount = 0
            if payment.payment_method == "COD":
                payment.payment_status = "Cancelled"
        db.commit()
        db.refresh(order)
        db.refresh(payment)
        return {"message": "Item cancelled successfully",
                "order_id": order.id,
                "cancelled_item_id": order_item.id,
                "refund_amount": actual_refund,
                "remaining_order_amount": order.total_amount,
                "order_status": order.status,
                "payment_status": payment.payment_status,
                "refund_status": payment.refund_status}
    order_items = db.query(OrderItems).filter(OrderItems.order_id == order.id).all()
    refund_amount = 0
    for order_item in order_items:
        if order_item.status == "Cancelled":
            continue
        product = db.query(Products).filter(Products.id == order_item.product_id).first()
        if product is not None:
            if order.status == "Awaiting Payment":
                if product.reserved_quantity >= order_item.quantity:
                    product.reserved_quantity -= order_item.quantity
                    product.stock_quantity += order_item.quantity
            elif order.status in ("Paid", "Processing"):
                product.stock_quantity += order_item.quantity
        order_item.status = "Cancelled"
        refund_amount += order_item.total_price
    order.total_amount = 0
    order.status = "Cancelled"
    if payment.payment_method == "COD":
        actual_refund = 0
        payment.payment_status = "Cancelled"
    else:
        if payment.payment_status == "Success":
            payment.refund_status = "Refunded"
            if payment.refunded_amount is None:
                payment.refunded_amount = refund_amount
            else:
                payment.refunded_amount += refund_amount
            payment.refund_transaction_id = str(uuid.uuid4())
            payment.refunded_at = datetime.utcnow()
            actual_refund = refund_amount
        else:
            payment.payment_status = "Cancelled"
            actual_refund = 0
    db.commit()
    db.refresh(order)
    db.refresh(payment)
    return {"message": "Order cancelled successfully",
            "order_id": order.id,
            "refund_amount": actual_refund,
            "remaining_order_amount": order.total_amount,
            "order_status": order.status,
            "payment_status": payment.payment_status,
            "refund_status": payment.refund_status}




@router.post("/{order_number}/return", status_code=status.HTTP_201_CREATED)
async def request_return(
    user: user_dependency,
    db: db_dependency,
    order_number: int,
    item_number: int,
    reason: str
):
    check_shopping_access(user)

    current_user = db.query(Users).filter(
        Users.id == user["id"]
    ).first()

    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not current_user.customer_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer account is inactive"
        )

    order = db.query(Orders).filter(
        Orders.id == order_number,
        Orders.user_id == user["id"]
    ).first()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    order_item = db.query(OrderItems).filter(
        OrderItems.id == item_number,
        OrderItems.order_id == order.id
    ).first()

    if order_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found"
        )

    if order_item.status != "Delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only delivered items can be returned"
        )

    existing_request = db.query(ReturnRequests).filter(
        ReturnRequests.order_item_id == order_item.id,
        ReturnRequests.status.in_(["Pending", "Approved"])
    ).first()

    if existing_request is not None:
        if existing_request.status == "Pending":
            detail = "Return request already exists for this item"
        else:
            detail = "Return request has already been approved for this item"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

    reason = reason.strip()

    if reason == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Return reason cannot be empty"
        )

    return_request = ReturnRequests(
        order_id=order.id,
        order_item_id=order_item.id,
        user_id=user["id"],
        reason=reason,
        status="Pending"
    )

    db.add(return_request)
    db.commit()
    db.refresh(return_request)

    return {
        "message": "Return request submitted successfully",
        "return_request_id": return_request.id,
        "order_id": order.id,
        "order_item_id": order_item.id,
        "reason": return_request.reason,
        "status": return_request.status
    }
