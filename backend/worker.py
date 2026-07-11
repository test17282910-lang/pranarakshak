"""
worker.py — Background alert checking loop and dispatch manager.
Periodically assesses active patient exposure risk and dispatches SMS/Email notifications.
"""

import logging
import asyncio
from datetime import datetime, timezone
from db import db
from app import classify_aqi, naqi_air_quality_tier
from data_fetcher import get_readings_for_location
from alerts import send_sms, send_email

logger = logging.getLogger(__name__)


def build_alert_sms_text(name: str, tier: str, raw_aqi: float, effective_aqi: float, condition: str, symptoms: list[str]) -> str:
    """Formats a concise clinical SMS warning."""
    icon = "🚨" if tier.lower() in ("high_risk", "critical") else "⚠️"
    sym_clause = f" with active {', '.join(symptoms)}" if symptoms else ""
    return (
        f"{icon} AQI ALERT: {name}, your personalized health risk is {tier.upper()}.\n"
        f"Local AQI is {round(raw_aqi)}, but your susceptibility{sym_clause} raises the "
        f"effective risk index to {round(effective_aqi)}.\n"
        f"Please check your dashboard for custom precautions immediately."
    )


def build_alert_email_html(name: str, tier: str, raw_aqi: float, effective_aqi: float, condition: str, severity: str, symptoms: list[str], trigger: str, why_be_careful: str, precautions: list[dict]) -> str:
    """Formats a premium clinical HTML email alert."""
    theme_color = "#e53e3e" if tier.lower() in ("high_risk", "critical") else "#dd6b20"
    
    prec_rows = ""
    for p in precautions[:5]:
        cat_badge = f"<span style='background-color:#edf2f7;color:#4a5568;padding:2px 6px;border-radius:4px;font-size:10px;text-transform:uppercase;font-weight:bold;margin-right:8px;'>{p['category']}</span>"
        prec_rows += f"<li style='margin-bottom:8px;font-size:14px;'>{cat_badge}{p['text']}</li>"

    symptoms_str = ", ".join(symptoms) if symptoms else "None reported"
    trigger_str = trigger if trigger else "None reported"

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e2e8f0;border-radius:8px;padding:24px;background-color:#ffffff;color:#1a202c;">
        <div style="text-align:center;padding-bottom:16px;border-bottom:1px solid #edf2f7;">
            <span style="font-size:48px;">🔬</span>
            <h1 style="color:{theme_color};margin:12px 0 4px;font-size:22px;font-weight:700;">Personalized AQI Health Warning</h1>
            <p style="color:#718096;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Clinical Atmosphere Alert System</p>
        </div>
        
        <div style="margin:20px 0;">
            <p style="font-size:16px;line-height:1.5;">Dear <strong>{name}</strong>,</p>
            <p style="font-size:15px;line-height:1.6;color:#2d3748;">
                Our forecasting model has detected that local particulate and gas levels are elevated. Based on your medical profile, your personal health risk has crossed into the <strong style="color:{theme_color};text-transform:uppercase;">{tier}</strong> tier.
            </p>
            
            <div style="background-color:#f7fafc;border-left:4px solid {theme_color};padding:16px;border-radius:4px;margin:20px 0;">
                <h4 style="margin:0 0 8px;font-size:14px;color:#4a5568;text-transform:uppercase;letter-spacing:0.5px;">Exposure Risk Summary</h4>
                <table style="width:100%;font-size:13px;border-collapse:collapse;">
                    <tr><td style="padding:4px 0;color:#718096;">Factual Local AQI</td><td style="padding:4px 0;text-align:right;font-weight:600;">{round(raw_aqi)}</td></tr>
                    <tr><td style="padding:4px 0;color:#718096;">Condition Shift ({condition} - {severity})</td><td style="padding:4px 0;text-align:right;font-weight:600;">+{round(effective_aqi - raw_aqi - len(symptoms)*4)}</td></tr>
                    <tr><td style="padding:4px 0;color:#718096;">Symptom Penalty ({len(symptoms)} active)</td><td style="padding:4px 0;text-align:right;font-weight:600;">+{len(symptoms)*4}</td></tr>
                    <tr style="border-top:1px solid #e2e8f0;"><td style="padding:8px 0 0;color:#2d3748;font-weight:700;">Effective Vulnerability AQI</td><td style="padding:8px 0 0;text-align:right;font-weight:700;color:{theme_color};font-size:16px;">{round(effective_aqi)}</td></tr>
                </table>
            </div>

            <div style="background-color:#fffaf0;border:1px solid #feebc8;padding:16px;border-radius:4px;margin:20px 0;font-size:13px;line-height:1.5;color:#7b341e;">
                <strong>Clinical Exacerbation Mechanism:</strong><br/>
                {why_be_careful}
            </div>

            <div style="margin:20px 0;">
                <h4 style="margin:0 0 12px;font-size:14px;color:#4a5568;text-transform:uppercase;">Top Recommended Safeguards</h4>
                <ul style="padding-left:20px;margin:0;line-height:1.6;color:#2d3748;">
                    {prec_rows}
                </ul>
            </div>
        </div>
        
        <div style="margin-top:28px;padding-top:16px;border-top:1px solid #edf2f7;text-align:center;font-size:11px;color:#a0aec0;line-height:1.5;">
            <p>You received this alert because you enabled automated safety notifications.<br/>
            Current profile: {condition.upper()} ({severity}) | Active Symptoms: {symptoms_str} | Triggers: {trigger_str}</p>
            <p style="margin-top:8px;">&copy; AQI Alert Personalized Health Assistant, India.</p>
        </div>
    </div>
    """


async def run_alert_check_cycle() -> dict:
    """
    Executes a complete scanning cycle over all active users.
    Determines exposure levels, checks threshold violations, enforces rate limits,
    dispatches SMS/Email warning logs, and saves history.
    """
    logger.info("⚡ Starting background alert check cycle...")
    
    # 1. Fetch active users with GPS coordinates
    active_users = await asyncio.to_thread(db.get_active_users)
    if not active_users:
        logger.info("No active users with GPS coordinates cached.")
        return {"users_scanned": 0, "alerts_sent": 0, "status": "completed"}
        
    users_scanned = 0
    alerts_sent = 0
    
    for user in active_users:
        user_id = user["id"]
        lat = float(user["last_known_lat"])
        lon = float(user["last_known_lon"])
        name = user.get("name", "Patient")
        
        users_scanned += 1
        
        try:
            # 2. Fetch current local atmospheric metrics
            df, _, live_aqi = await asyncio.to_thread(get_readings_for_location, lat, lon)
            
            # Use current live reading, or fallback to 100 if both APIs fail
            current_aqi = live_aqi if live_aqi is not None else 100.0
            
            # 3. Personalise classification
            condition = user.get("condition", "other")
            severity = user.get("severity", "moderate")
            symptoms = user.get("symptoms", [])
            personalized_issue = user.get("personalized_issue", "")
            
            tier, alert_message, precautions, risk_explanation = classify_aqi(
                aqi=current_aqi,
                condition=condition,
                severity=severity,
                symptoms=symptoms,
                personalized_issue=personalized_issue,
                patient_name=name
            )
            
            effective_aqi = risk_explanation["effective_aqi"]
            threshold = user.get("alert_threshold", 100) or 100
            
            # 4. Check if risk threshold is crossed (or if tier is critical/high risk)
            is_risk_crossed = (effective_aqi >= threshold) or (tier.lower() in ("high_risk", "critical"))
            
            if not is_risk_crossed:
                # User matches safe limits — skip notification dispatch
                continue
                
            # 5. Dispatch alerts if enabled & permitted by rate-limiting (cooldown 12h)
            prediction_id = None  # Background check matches real-time sensor query
            
            # Check SMS channel (actually WhatsApp now)
            if user.get("sms_alerts_enabled", True) and user.get("phone"):
                phone = user["phone"]
                should_send, reason = await asyncio.to_thread(
                    db.should_send_alert, user_id, "whatsapp", tier, 12
                )
                
                if should_send:
                    # Use detailed WhatsApp format instead of SMS
                    whatsapp_text = f"""🚨 Pranarakshak Alert

AQI {round(effective_aqi)} crossed your threshold ({threshold})

{tier.upper()} Risk Level for {condition.upper()}

📍 Current AQI: {round(raw_aqi)}
🔴 Your Risk Level: {round(effective_aqi)}
⚕️ Health Impact: {condition} ({severity})

🛡️ Immediate Actions:
• {precautions[0]['text'] if precautions else 'Stay indoors'}
• {precautions[1]['text'] if len(precautions) > 1 else 'Use air purifier'}

📱 View full details: https://pranarakshak-six.vercel.app/dashboard

Stay safe! 💙 Pranarakshak"""

                    from alerts import send_whatsapp
                    status, provider_id = send_whatsapp(phone, whatsapp_text)
                    
                    # Log dispatch details
                    alert_log = {
                        "user_id": user_id,
                        "alert_tier": tier,
                        "channel": "whatsapp",
                        "status": status,
                        "suppressed_reason": None if status == "sent" else provider_id,
                        "alert_message": whatsapp_text,
                        "precautions": str([p["text"] for p in precautions[:3]]),
                        "provider_id": provider_id if status == "sent" else None
                    }
                    await asyncio.to_thread(db.log_alert, alert_log)
                    if status == "sent":
                        alerts_sent += 1
                else:
                    # Suppressed due to cooldown/rate limits
                    logger.info(f"WhatsApp suppressed for user {name} due to: {reason}")
                    
            # Check Email channel
            if user.get("email_alerts_enabled", True) and user.get("email"):
                email = user["email"]
                should_send, reason = await asyncio.to_thread(
                    db.should_send_alert, user_id, "email", tier, 12
                )
                
                if should_send:
                    subject = f"⚠️ Clinical AQI Health Warning: {tier.upper()} Personal Risk Level"
                    html_content = build_alert_email_html(
                        name=name,
                        tier=tier,
                        raw_aqi=current_aqi,
                        effective_aqi=effective_aqi,
                        condition=condition,
                        severity=severity,
                        symptoms=symptoms,
                        trigger=personalized_issue,
                        why_be_careful=risk_explanation["why_be_careful"],
                        precautions=precautions
                    )
                    status, provider_id = send_email(email, subject, html_content)
                    
                    # Log dispatch details
                    alert_log = {
                        "user_id": user_id,
                        "alert_tier": tier,
                        "channel": "email",
                        "status": status,
                        "suppressed_reason": None if status == "sent" else provider_id,
                        "alert_message": f"Subject: {subject}",
                        "precautions": str([p["text"] for p in precautions[:3]]),
                        "provider_id": provider_id if status == "sent" else None
                    }
                    await asyncio.to_thread(db.log_alert, alert_log)
                    if status == "sent":
                        alerts_sent += 1
                else:
                    # Suppressed due to cooldown/rate limits
                    logger.info(f"Email suppressed for user {name} due to: {reason}")
                    
        except Exception as exc:
            logger.error(f"Error checking alerts for user {name} ({user_id}): {exc}")
            
    logger.info(f"⚡ Alert check cycle complete. Scanned {users_scanned} users. Sent {alerts_sent} dispatches.")
    return {"users_scanned": users_scanned, "alerts_sent": alerts_sent, "status": "completed"}
