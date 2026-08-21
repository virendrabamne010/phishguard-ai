import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ml.predict import predict_email, _load_artifacts

# reload to ensure it uses the latest model
_load_artifacts()

subject = "Meeting at 3 PM"
body = "Hey team, just a reminder that we have a meeting at 3 PM today in conference room A. Thanks!"
sender = "boss@company.com"

print("Predicting Normal Email...")
res = predict_email(subject, body, sender)
print(res)

subject2 = "URGENT: Your account will be locked"
body2 = "Please click here to verify your account immediately: http://192.168.1.1/login"
sender2 = "admin@security-alert.com"
print("\nPredicting Phishing Email...")
res2 = predict_email(subject2, body2, sender2)
print(res2)
