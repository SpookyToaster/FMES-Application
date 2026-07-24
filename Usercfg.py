#placeholder where user preferences and custom configurations can be defined


# Instantiate a list of users
# Each user should be able to reply to the email notification to add or remove reports based on a provided list
# EXAMPLE: 

# ====================================================
# Hello User,
# 
# here is the list of reports you are subscribed to. You can reply to this email to add or remove reports from your subscription.
#
# Report 1: Example Report A
# Report 2: Example Report B
# Report 3: Example Report C
#
#
# If you would like to remove or add a report, reply to this email in this exact format:
#
# To see a list of available reports, reply with SEE REPORTS
#
# To add a report: ADD Report Name
# To remove a report: REMOVE Report Name
#
# ADD DAILY MOLD SCHEDULE REPORT
# REMOVE DAILY MELT POUNDS
#
# ====================================================

class UserConfig:
    # User-specific configurations can be added here
    ADD_REPORTS = ["DAILY MOLD SCHEDULE REPORT"]
    REMOVE_REPORTS = ["DAILY MELT POUNDS"]

    # You can add more user-specific configurations below if needed
    EMAIL_NOTIFICATIONS_ENABLED = True
    EMAIL_ADDRESS = "user@example.com"
    EMAIL_SMTP_SERVER = "smtp.example.com"
    EMAIL_SMTP_PORT = 587
    EMAIL_USERNAME = "user@example.com"
    EMAIL_PASSWORD = "your_email_password"
    EMAIL_USE_TLS = True
    EMAIL_USE_SSL = False
    EMAIL_TIMEOUT = 60  # Timeout for email server connection in seconds
    EMAIL_DEBUG = False  # Enable debug output for email server connection
