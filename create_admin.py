from database import SessionLocal
from models import Admins
from passlib.context import CryptContext


bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


db = SessionLocal()


username = input("Enter admin username: ")
email = input("Enter admin email: ")
password = input("Enter admin password: ")
first_name = input("Enter admin first name: ")
last_name = input("Enter admin last name: ")
phone_number = input("Enter admin phone number: ")


existing_username = db.query(Admins).filter(
    Admins.username == username
).first()

if existing_username:
    print("Username already exists.")
    db.close()
    exit()


existing_email = db.query(Admins).filter(
    Admins.email == email
).first()

if existing_email:
    print("Email already exists.")
    db.close()
    exit()


hashed_password = bcrypt_context.hash(password)


admin = Admins(
    username=username,
    email=email,
    first_name=first_name,
    last_name=last_name,
    hashed_password=hashed_password,
    phone_number=phone_number,
    is_active=True
)


db.add(admin)
db.commit()
db.refresh(admin)


print("Admin created successfully.")
print("Admin ID:", admin.id)
print("Username:", admin.username)


db.close()