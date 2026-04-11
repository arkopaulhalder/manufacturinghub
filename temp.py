from werkzeug.security import generate_password_hash

password = "Admin@123"
print(generate_password_hash(password))
