"""
test_alerts.py — Quick Alert System Test Script

Run this to verify your Twilio SMS and SendGrid Email setup.
"""

import os
from dotenv import load_dotenv
from alerts import send_sms, send_email

load_dotenv()

def test_alerts():
    print("=" * 60)
    print("🧪 Pranarakshak Alert System Test")
    print("=" * 60)
    
    # Get test contact info
    print("\n📋 Enter test contact details:")
    test_phone = input("Your phone number (with country code, e.g., +919999999999): ").strip()
    test_email = input("Your email address: ").strip()
    
    print("\n" + "=" * 60)
    print("Testing SMS Alert...")
    print("=" * 60)
    
    sms_body = """
🚨 Pranarakshak AQI Alert (TEST)

Your personalized AQI forecast shows HIGH RISK.
Current AQI: 185 (Unhealthy)

⚠️ PRECAUTIONS:
• Stay indoors
• Use N95 mask if going out
• Keep rescue inhaler ready

This is a test alert.
""".strip()
    
    status, sid = send_sms(test_phone, sms_body)
    print(f"📱 SMS Status: {status}")
    print(f"📱 Message ID: {sid}")
    
    if status == "sent":
        print("✅ SMS sent successfully!")
    else:
        print(f"❌ SMS failed: {sid}")
    
    print("\n" + "=" * 60)
    print("Testing Email Alert...")
    print("=" * 60)
    
    email_subject = "🚨 Pranarakshak AQI Alert (TEST)"
    email_body = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                  color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 30px; }
        .alert-box { background: #fff3cd; border-left: 4px solid #ffc107; 
                     padding: 15px; margin: 20px 0; }
        .precautions { background: white; padding: 20px; border-radius: 8px; 
                       box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .precautions li { margin: 10px 0; }
        .footer { text-align: center; padding: 20px; color: #777; font-size: 12px; }
        .btn { display: inline-block; padding: 12px 24px; background: #667eea; 
               color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 AQI Health Alert</h1>
            <p style="margin: 0; opacity: 0.9;">Pranarakshak Air Quality Intelligence</p>
        </div>
        
        <div class="content">
            <div class="alert-box">
                <h2 style="margin-top: 0; color: #856404;">⚠️ HIGH RISK DETECTED (TEST)</h2>
                <p><strong>Current AQI:</strong> 185 (Unhealthy)</p>
                <p><strong>Forecast:</strong> Air quality will remain poor for the next 6 hours</p>
                <p><strong>Your Risk Level:</strong> High (based on your Asthma - Moderate profile)</p>
            </div>
            
            <div class="precautions">
                <h3>🛡️ Personalized Precautions</h3>
                <ul>
                    <li><strong>Stay Indoors:</strong> Minimize outdoor exposure today</li>
                    <li><strong>Use N95 Mask:</strong> If you must go outside, wear a well-fitted mask</li>
                    <li><strong>Medication Ready:</strong> Keep your rescue inhaler accessible</li>
                    <li><strong>Air Purifier:</strong> Run it in your main living space</li>
                    <li><strong>Watch Symptoms:</strong> Monitor for coughing, wheezing, or chest tightness</li>
                </ul>
            </div>
            
            <p style="text-align: center;">
                <a href="https://pranarakshak-six.vercel.app/dashboard" class="btn">
                    View Dashboard →
                </a>
            </p>
            
            <p style="font-size: 14px; color: #666; border-top: 1px solid #ddd; 
                      padding-top: 20px; margin-top: 30px;">
                <strong>Why this alert?</strong><br>
                This is a TEST alert. Our AI model detected elevated AQI levels at your location 
                and calculated a high risk based on your respiratory condition. Real alerts will 
                be sent when actual dangerous conditions are detected.
            </p>
        </div>
        
        <div class="footer">
            <p>This is an automated alert from Pranarakshak.<br>
            To stop receiving alerts, update your preferences in the dashboard.</p>
            <p style="margin-top: 10px;">
                <small>© 2026 Pranarakshak. Environmental health intelligence for India.</small>
            </p>
        </div>
    </div>
</body>
</html>
""".strip()
    
    status, msg_id = send_email(test_email, email_subject, email_body)
    print(f"📧 Email Status: {status}")
    print(f"📧 Message ID: {msg_id}")
    
    if status == "sent":
        print("✅ Email sent successfully!")
    else:
        print(f"❌ Email failed: {msg_id}")
    
    print("\n" + "=" * 60)
    print("🏁 Test Complete")
    print("=" * 60)
    
    print("\n📊 Results Summary:")
    print(f"SMS:   {'✅ Working' if status == 'sent' else '❌ Check logs'}")
    print(f"Email: {'✅ Working' if status == 'sent' else '❌ Check logs'}")
    
    print("\n💡 Next Steps:")
    if "mock" in sid.lower() or "mock" in msg_id.lower():
        print("⚠️  You're in MOCK mode (no real alerts sent)")
        print("   → Add real Twilio/SendGrid credentials to Railway")
        print("   → See ALERT_SETUP.md for detailed instructions")
    else:
        print("✅ Real alerts are working!")
        print("   → Check your phone and email inbox")
        print("   → Deploy worker.py for automated monitoring")
    
    print("\n")

if __name__ == "__main__":
    test_alerts()
