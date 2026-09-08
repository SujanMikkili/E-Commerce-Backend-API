from fastapi import FastAPI
import models
from database import engine
from routers import admin,auth,cart,orders,payments,products,users,registration

app=FastAPI()
models.Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(products.router)
app.include_router(users.router)
app.include_router(registration.router)


