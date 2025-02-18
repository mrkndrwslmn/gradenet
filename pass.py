from werkzeug.security import generate_password_hash

def hash_password():
    password = input("Enter your password: ")
    print("\nChoose a hashing method:")
    print("1. pbkdf2:sha256 (default in Flask)")
    print("2. bcrypt")
    
    choice = input("Enter your choice (1 or 2): ")
    method = "pbkdf2:sha256" if choice == "1" else "bcrypt"

    hashed_password = generate_password_hash(password, method=method)
    
    print(f"\nHashed Password ({method}): {hashed_password}")

if __name__ == "__main__":
    hash_password()
