# E-Commerce Backend API

A backend REST API for a e-commerce platform built with
**FastAPI, SQLAlchemy, PostgreSQL, JWT authentication, and role-based
access control**. The system supports customer and seller registration,
product management with admin approval, shopping carts, order creation,
COD/UPI/CARD payment flows, order cancellation, item-level returns,
refunds, inventory reservation, and admin return/product management.

## Project Overview

This project implements the backend business logic for an e-commerce
marketplace with three main roles:

-   **Customer** -- browse approved products, manage cart and addresses, place orders, make payments, cancel orders, and request item-level returns.

-   **Seller** -- has the same shopping capabilities as a customer and can additionally create, manage, update, and delete their own products and maintain seller/store information.

-   **Admin** -- manage product approvals/rejections, administer return requests, process refunds, and update the admin profile.


The application is organized as a FastAPI application with separate
routers for authentication, registration, users, products, cart, orders,
payments, and administration.

## Key Features

### Authentication & Authorization

-   Customer, seller, and admin authentication.
-   JWT access-token based authentication.
-   Password hashing using `passlib`/bcrypt.
-   Role-based access checks for customer/seller/admin operations.
-   Token expiration handling.
-   Inactive-user and inactive-admin checks.

The authentication module creates JWT claims containing the username,
user ID, and role, and protects API routes through FastAPI dependencies.

### Customer & Seller Registration

-   Customer registration with automatic cart creation.
-   Seller registration with store name and store description.
-   Seller records linked to user accounts.
-   Passwords stored as hashes rather than plain text.

### Product Management

-   Sellers can create products.
-   Newly created products start in `Pending` approval status.
-   Sellers can view their own products.
-   Sellers can update or delete their products.
-   Updating a product sends it back to `Pending` approval.
-   Customers can view only approved products.
-   Admins can approve or reject pending products.
-   Admin rejection reasons are stored with the product.

### Shopping Cart

-   View the current user's cart.
-   Add products to the cart.
-   Increase quantity for an existing cart item.
-   Update cart item quantities.
-   Remove individual cart items.
-   Stock validation before adding or updating quantities.
-   Cart is created automatically during customer/seller registration.

### Orders

-   Create an order from the complete cart.
-   Buy a single cart item directly.
-   Validate shipping address and product availability.
-   Support `COD`, `UPI`, and `CARD` payment methods.
-   Create order-item records for each purchased product.
-   Reserve inventory when an order is created.
-   Automatically clear purchased items from the cart.
-   View all customer orders.
-   View an individual order with its order items.

### Payment Flow

The project contains a simulated payment workflow rather than a real
payment-gateway integration.

Supported payment methods:

-   Cash on Delivery (COD)
-   UPI
-   Card

Payment features include:

-   Pending payment records when an order is created.
-   Successful payment simulation.
-   Payment failure simulation.
-   Transaction ID generation using UUID.
-   Payment timestamps.
-   Payment status retrieval.
-   Inventory restoration and cart restoration after simulated payment
    failure.

### Order Cancellation

The cancellation logic supports both:

-   **Individual order-item cancellation**
-   **Complete order cancellation**

The implementation handles inventory restoration and payment state based
on the cancellation scenario.

For partial cancellation:

-   The cancelled item is marked `Cancelled`.
-   The cancelled item's amount is removed from the order total.
-   COD remains active when other items remain.
-   Online payments record the cancelled amount as a refund when the
    original payment was successful.

For complete cancellation:

-   All active items are cancelled.
-   The order total becomes zero.
-   The order status becomes `Cancelled`.
-   COD payment is cancelled.
-   Successful online payments record the refund amount.

### Returns & Refunds

-   Returns are requested for individual order items.
-   Only delivered items can be returned.
-   A return request must contain a reason.
-   Duplicate pending/approved return requests for the same item are
    prevented.
-   Requests are stored in a dedicated `return_requests` table.
-   Admins can approve or reject return requests.
-   Approved online-payment returns record refund amount, refund
    transaction ID, refund status, and refund timestamp.
-   Returned product quantities are added back to stock.
-   The order can become `Returned` when all items have been
    returned/cancelled and at least one item was returned.

## Technology Stack

  Technology          Purpose
  ------------------- ---------------------------------
  Python              Backend programming language
  FastAPI             REST API framework
  SQLAlchemy          ORM and database access
  PostgreSQL          Relational database
  Pydantic            Request/response validation
  JWT / python-jose   Authentication tokens
  Passlib + bcrypt    Password hashing
  python-dotenv       Environment variable management
  Uvicorn             ASGI application server

## Project Structure

``` text
project/
│
├── main.py
├── database.py
├── models.py
├── create_admin.py
│
├── routers/
│   ├── auth.py
│   ├── registration.py
│   ├── users.py
│   ├── products.py
│   ├── cart.py
│   ├── orders.py
│   ├── payments.py
│   └── admin.py
│
├── .env
├── .gitignore
└── README.md
```

> The exact folder structure assumes the uploaded router files are
> placed inside a `routers/` package, which matches how `main.py`
> imports them.

## Database Design

The SQLAlchemy models define the following main entities:

-   `Users`
-   `Admins`
-   `Sellers`
-   `Addresses`
-   `Products`
-   `Cart`
-   `CartItems`
-   `Orders`
-   `OrderItems`
-   `Payments`
-   `ReturnRequests`

Important relationships include:

``` text
Users
 ├── Addresses
 ├── Cart
 │    └── CartItems ─── Products
 ├── Orders
 │    └── OrderItems ─── Products
 └── Sellers
      └── Products

Orders
 └── Payments

Orders
 └── ReturnRequests
       └── OrderItems
```

The product model maintains both `stock_quantity` and
`reserved_quantity`, allowing the application to distinguish available
inventory from inventory reserved for orders.

## API Modules

### Authentication

``` text
POST /auth/token
```

Authenticates a customer, seller, or admin and returns a bearer access
token.

### Registration

``` text
POST /auth/customer
POST /auth/seller
```

### Users

``` text
GET    /users/me
POST   /users/address
GET    /users/addresses
PUT    /users/address/{address_id}
PUT    /users/me/phone_number
DELETE /users/me
```

### Products

``` text
GET    /products/
GET    /products/{product_id}
POST   /products/
GET    /products/my-products
PUT    /products/my-products/{product_number}
DELETE /products/{product_number}
```

### Cart

``` text
GET    /cart/
POST   /cart/items
PUT    /cart/items/{item_id}
DELETE /cart/items/{item_id}
```

### Orders

``` text
POST /orders/
POST /orders/buy-item/{item_number}
GET  /orders/
GET  /orders/{order_number}
PUT  /orders/{order_number}/cancel
POST /orders/{order_number}/return
```

### Payments

``` text
POST /payments/{order_number}/pay
GET  /payments/{order_number}
```

### Admin

``` text
PUT /admin/returns/profile

GET /admin/returns/products/pending
PUT /admin/returns/products/{product_id}/approve
PUT /admin/returns/products/{product_id}/reject

GET /admin/returns/
PUT /admin/returns/{request_id}/approve
PUT /admin/returns/{request_id}/reject
```

## Order & Inventory Flow

``` text
Customer
   │
   ├── Browse approved products
   │
   ├── Add product to cart
   │
   ├── Create order
   │       │
   │       ├── Validate stock
   │       ├── Decrease available stock
   │       ├── Increase reserved stock
   │       ├── Create order items
   │       └── Create pending payment
   │
   └── Complete payment
           │
           ├── Success
           │     ├── Convert reserved inventory
           │     └── Mark order Paid
           │
           └── Failure
                 ├── Restore stock
                 ├── Remove reserved quantity
                 ├── Restore items to cart
                 └── Mark payment/order as failed
```

## Return Flow

``` text
Delivered Order Item
        │
        ▼
Customer submits return request
        │
        ▼
ReturnRequests
Status = Pending
        │
        ├───────────────┐
        ▼               ▼
     Approve          Reject
        │               │
        ▼               ▼
 Mark item Returned   Status = Rejected
        │
        ├── Restore stock
        │
        └── Online payment?
                │
          ┌─────┴─────┐
          ▼           ▼
         Yes          COD
          │           │
          ▼           ▼
       Record      No monetary
       refund       refund
```

## Setup

### 1. Clone the repository

``` bash
git clone <your-repository-url>
cd <your-repository-folder>
```

### 2. Create a virtual environment

Windows:

``` bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

``` bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

``` bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-jose[cryptography] passlib[bcrypt] python-multipart python-dotenv
```

### 4. Configure environment variables

Create a local `.env` file:

``` env
DATABASE_URL=postgresql://<username>:<password>@localhost/<database_name>
SECRET_KEY=<strong-random-secret>
```

Do not commit the `.env` file to GitHub.

### 5. Create the database

Create a PostgreSQL database matching the database name in your local
`DATABASE_URL`.

The application creates the SQLAlchemy tables when the FastAPI
application starts.

### 6. Create an admin account

Run:

``` bash
python create_admin.py
```

The script prompts for the admin username, email, password, name, and
phone number and stores the password as a hash.

### 7. Start the API

``` bash
uvicorn main:app --reload
```

Open the FastAPI Swagger UI:

``` text
http://127.0.0.1:8000/docs
```

## Example Workflow

A typical marketplace workflow is:

``` text
1. Register customer
2. Register seller
3. Seller creates product
4. Admin reviews product
5. Admin approves product
6. Customer logs in
7. Customer adds product to cart
8. Customer creates order
9. Customer completes COD/UPI/Card payment flow
10. Order becomes Paid
11. Order is processed and delivered
12. Customer can request a return for a delivered item
13. Admin approves/rejects the return
14. Approved return restores stock and records refund information for online payments
```

## Security Notes

-   Passwords are hashed using bcrypt before being stored.
-   JWT tokens are used for authenticated API access.
-   Role-based authorization prevents customers/sellers from accessing
    admin functionality.
-   Environment variables are used for the database connection and JWT
    secret.

**Important:** Never commit real database credentials or JWT secrets. If
credentials have ever been exposed publicly, replace/rotate them before
publishing the repository.

## Current Scope / Limitations

This project focuses on backend API and business logic. Based on the
current source code:

-   Payment processing is simulated; there is no external payment
    gateway integration.
-   No frontend application is included.
-   No automated test suite is included in the uploaded project.
-   Database migrations are not included; table creation currently
    occurs through `Base.metadata.create_all()` when the application
    starts.
-   Product/order/return workflow is implemented through API endpoints,
    but production deployment concerns such as rate limiting,
    centralized logging, monitoring, and background jobs are outside the
    current scope.

## Why This Project Is Useful

This project demonstrates practical backend development concepts
including:

-   REST API development with FastAPI
-   JWT authentication and role-based authorization
-   SQLAlchemy ORM and relational database modeling
-   PostgreSQL integration
-   E-commerce cart and order workflows
-   Inventory reservation and restoration
-   Payment state management
-   Partial and complete order cancellation
-   Item-level return processing
-   Refund tracking
-   Admin approval workflows
-   Input validation and HTTP error handling

## Author

**Sujan Mikkili**

Backend project demonstrating FastAPI, PostgreSQL, SQLAlchemy,
authentication, authorization, and e-commerce business logic.
