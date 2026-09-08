from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from sqlalchemy.orm import Session
from starlette import status
from datetime import datetime
import uuid
from database import SessionLocal
from models import Orders,OrderItems,Payments,Products,ReturnRequests,Admins
from .auth import get_current_user
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/admin/returns",tags=["Admin Returns"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


class ProductRejectionRequest(BaseModel):
    rejection_reason: str


def check_admin(user:user_dependency, db:db_dependency):
    admin = db.query(Admins).filter(Admins.id == user["id"]).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Admin not found")
    if not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Admin account is inactive")
    if user["user_role"] != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Admin access required")
    return admin


@router.put("/profile", status_code=status.HTTP_200_OK)
async def update_admin(user: user_dependency,db: db_dependency,
                       username: Optional[str] = None,email: Optional[str] = None,
                       first_name: Optional[str] = None,last_name: Optional[str] = None,
                       phone_number: Optional[str] = None):
    admin = check_admin(user, db)
    if username is not None:
        admin.username = username
    if email is not None:
        admin.email = email
    if first_name is not None:
        admin.first_name = first_name
    if last_name is not None:
        admin.last_name = last_name
    if phone_number is not None:
        admin.phone_number = phone_number
    db.commit()
    db.refresh(admin)
    return {"message": "Admin details updated successfully",
            "admin": admin}



@router.get("/products/pending", status_code=status.HTTP_200_OK)
async def get_pending_products(db: db_dependency,user: user_dependency):
    check_admin(user,db)
    products = db.query(Products).filter(Products.approval_status == "Pending").all()
    return products


@router.put("/products/{product_id}/approve",status_code=status.HTTP_200_OK)
async def approve_product(product_id: int,db: db_dependency,user: user_dependency):
    check_admin(user,db)
    product = db.query(Products).filter(Products.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found")
    if product.approval_status != "Pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Product is not pending approval")
    product.approval_status = "Approved"
    product.reviewed_by = user["id"]
    product.rejection_reason = None
    db.commit()
    db.refresh(product)
    return {"message": "Product approved successfully","product_id": product.id}


@router.put("/products/{product_id}/reject",status_code=status.HTTP_200_OK)
async def reject_product(product_id: int,rejection_request: ProductRejectionRequest,
                         db: db_dependency,user: user_dependency):
    check_admin(user,db)
    product = db.query(Products).filter(Products.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Product not found")
    if product.approval_status != "Pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Product is not pending approval")
    product.approval_status = "Rejected"
    product.reviewed_by = user["id"]
    product.rejection_reason = rejection_request.rejection_reason
    db.commit()
    db.refresh(product)
    return {"message": "Product rejected successfully",
            "product_id": product.id,
            "rejection_reason": product.rejection_reason}


@router.get("/", status_code=status.HTTP_200_OK)
async def get_return_requests(user: user_dependency,db: db_dependency):
    check_admin(user, db)
    requests = db.query(ReturnRequests).filter(ReturnRequests.status == "Pending").order_by(ReturnRequests.id).all()
    result = []
    for return_request in requests:
        result.append({"return_request_id": return_request.id,
                       "order_id": return_request.order_id,
                       "order_item_id": return_request.order_item_id,
                       "user_id": return_request.user_id,
                       "reason": return_request.reason,
                       "status": return_request.status,
                       "requested_at": return_request.requested_at})
    return result


@router.put("/{request_id}/approve", status_code=status.HTTP_200_OK)
async def approve_return(request_id: int,user: user_dependency,db: db_dependency):
    check_admin(user, db)
    return_request = db.query(ReturnRequests).filter(ReturnRequests.id == request_id).first()
    if return_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Return request not found")
    if return_request.status != "Pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Return request is already {return_request.status}")
    order = db.query(Orders).filter(Orders.id == return_request.order_id).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Order not found")
    order_item = db.query(OrderItems).filter(OrderItems.id == return_request.order_item_id,
                                             OrderItems.order_id == order.id).first()
    if order_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Order item not found")
    if order_item.status != "Delivered":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Only delivered items can be returned. Current status: {order_item.status}")
    payment = db.query(Payments).filter(Payments.order_id == order.id).first()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Payment record not found")
    refund_amount = order_item.total_price
    actual_refund = 0
    if payment.payment_method != "COD":
        if payment.payment_status != "Success":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Payment was not successfully completed")
        if payment.refunded_amount is None:
            payment.refunded_amount = refund_amount
        else:
            payment.refunded_amount += refund_amount
        payment.refund_status = "Refunded"
        payment.refund_transaction_id = str(uuid.uuid4())
        payment.refunded_at = datetime.utcnow()
        actual_refund = refund_amount
    else:
        actual_refund = 0
    product = db.query(Products).filter(Products.id == order_item.product_id).first()
    if product is not None:
        product.stock_quantity += order_item.quantity
    order_item.status = "Returned"
    return_request.status = "Approved"
    return_request.approved_at = datetime.utcnow()
    order_items = db.query(OrderItems).filter(OrderItems.order_id == order.id).all()
    all_returned_or_cancelled = True
    for item in order_items:
        if item.status not in ("Returned", "Cancelled"):
            all_returned_or_cancelled = False
            break
    if all_returned_or_cancelled:
        has_returned_item = False
        for item in order_items:
            if item.status == "Returned":
                has_returned_item = True
                break
        if has_returned_item:
            order.status = "Returned"
    db.commit()
    db.refresh(return_request)
    db.refresh(order)
    db.refresh(order_item)
    db.refresh(payment)
    return {"message": "Return approved successfully",
            "return_request_id": return_request.id,
            "order_id": order.id,
            "order_item_id": order_item.id,
            "refund_amount": actual_refund,
            "refund_status": payment.refund_status,
            "refund_transaction_id": payment.refund_transaction_id,
            "order_item_status": order_item.status,
            "order_status": order.status}



@router.put("/{request_id}/reject", status_code=status.HTTP_200_OK)
async def reject_return(request_id: int,user: user_dependency,db: db_dependency):
    check_admin(user, db)
    return_request = db.query(ReturnRequests).filter(ReturnRequests.id == request_id).first()
    if return_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Return request not found")
    if return_request.status != "Pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f"Return request is already {return_request.status}")
    return_request.status = "Rejected"
    return_request.rejected_at = datetime.utcnow()
    db.commit()
    db.refresh(return_request)
    return {"message": "Return request rejected",
            "return_request_id": return_request.id,
            "status": return_request.status}
