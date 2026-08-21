# Deployment checklist

## 1. Environment preparation
- Set strong values for SECRET_KEY, ADMIN_USERNAME, and ADMIN_PASSWORD.
- Ensure the backend .env file exists and points to the intended database.
- Confirm the frontend API base URL is correct for your hosting environment.

## 2. Infrastructure readiness
- Provision a host or container platform with enough memory for the backend and frontend processes.
- Expose the backend on HTTPS and configure reverse proxy rules if needed.
- Set up persistent storage for the database and uploaded artifacts.

## 3. Security hardening
- Replace default credentials and disable debug mode in production.
- Restrict CORS origins to your real deployment domains.
- Set `TRUSTED_HOSTS` to the final production hostname(s).
- Add TLS certificates and enforce HTTPS.
- Confirm `backend/.env.example` is not reused as-is and rotate any previously exposed local secrets.

## 4. Monitoring and operations
- Configure health checks for backend and frontend services.
- Add logs, uptime monitoring, and alerting.
- Plan backup and recovery procedures for the database.
- Verify IMAP session persistence remains encrypted at rest and that file permissions are limited to the service user.

## 5. Delivery validation
- Confirm the backend health and readiness endpoints respond successfully.
- Verify the dashboard loads and the login flow works.
- Run the backend and frontend test/build commands before release.
