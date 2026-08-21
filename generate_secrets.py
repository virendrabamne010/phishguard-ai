import secrets
import string

def generate_secret(length=32):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Removing some tricky characters for bash/docker environment variables
    alphabet = alphabet.replace("'", "").replace('"', "").replace("\\", "").replace("`", "")
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_env_file():
    secret_key = generate_secret(64)
    admin_password = generate_secret(20)
    postgres_password = generate_secret(32)

    env_content = f"""# Production Environment Variables
ENVIRONMENT=production
DEBUG=False

# Backend App Settings
SECRET_KEY="{secret_key}"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="{admin_password}"
PORT=8000
HOST=0.0.0.0

# Database Settings
POSTGRES_PASSWORD="{postgres_password}"
DATABASE_URL=postgresql://phishguard:{postgres_password}@db:5432/phishguard

# Frontend & CORS Settings
FRONTEND_URL=http://localhost
REDIRECT_URI=http://localhost/api/inbox/oauth/callback
CORS_ORIGINS=http://localhost
TRUSTED_HOSTS=localhost,127.0.0.1
"""

    with open(".env.production", "w") as f:
        f.write(env_content)
    
    print("Generated secure .env.production file. Make sure to review the values, especially FRONTEND_URL and CORS_ORIGINS for your actual domain.")

if __name__ == "__main__":
    generate_env_file()
