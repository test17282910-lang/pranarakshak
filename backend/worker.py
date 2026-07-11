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


def build_alert_email_html(name: str, tier: str, raw_aqi: float, effective_aqi: float, condition: str, severity: str, symptoms: list[str], trigger: str, why_be_careful: str, precautions: list[dict], symptom_weighted_penalties: dict | None = None) -> str:
    """Formats a premium clinical HTML email alert."""
    theme_color = "#e53e3e" if tier.lower() in ("high_risk", "critical") else "#dd6b20"
    
    prec_rows = ""
    for p in precautions[:5]:
        cat_badge = f"<span style='background-color:#edf2f7;color:#4a5568;padding:2px 6px;border-radius:4px;font-size:10px;text-transform:uppercase;font-weight:bold;margin-right:8px;'>{p['category']}</span>"
        prec_rows += f"<li style='margin-bottom:8px;font-size:14px;'>{cat_badge}{p['text']}</li>"

    symptoms_str = ", ".join(symptoms) if symptoms else "None reported"
    trigger_str = trigger if trigger else "None reported"

    # Use actual weighted penalties — never fall back to the flat len*4 formula
    if symptom_weighted_penalties and symptom_weighted_penalties:
        actual_symptom_penalty = sum(symptom_weighted_penalties.values())
        # e.g. ": Wheezing +8, ShortnessOfBreath +12, NighttimeSymptoms +4"
        symptom_breakdown_str = ": " + ", ".join(
            f"{s} +{w}" for s, w in symptom_weighted_penalties.items()
        ) if symptom_weighted_penalties else ""
    else:
        # Fallback only if weights weren't passed (older callers)
        actual_symptom_penalty = len(symptoms) * 4
        symptom_breakdown_str = ""

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
                    <tr><td style="padding:4px 0;color:#718096;">Condition Shift ({condition} - {severity})</td><td style="padding:4px 0;text-align:right;font-weight:600;">+{round(effective_aqi - raw_aqi - actual_symptom_penalty)}</td></tr>
                    <tr><td style="padding:4px 0;color:#718096;">Symptom Penalty ({len(symptoms)} active{symptom_breakdown_str})</td><td style="padding:4px 0;text-align:right;font-weight:600;">+{actual_symptom_penalty}</td></tr>
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
            
            # ═══════════════════════════════════════════════════════════════════════════
            # NEW FEATURES: Check medication reminders, family alerts, emergency contacts
            # ═══════════════════════════════════════════════════════════════════════════
            
            # Feature 3: Medication Reminder Integration
            if effective_aqi >= threshold:
                await check_and_send_medication_reminders(user, current_aqi, tier)
            
            # Feature 4: Family Group Alerts (for high risk and critical)
            if tier.lower() in ("high_risk", "critical"):
                await send_family_group_alerts(user, tier, current_aqi, effective_aqi)
            
            # Feature 8: Emergency Contact Auto-Alert (critical only)
            if tier.lower() == "critical":
                await trigger_emergency_contact_alerts(user, current_aqi)
            
            # ═══════════════════════════════════════════════════════════════════════════
            # ORIGINAL ALERT SYSTEM (WhatsApp + Email)
            # ═══════════════════════════════════════════════════════════════════════════
            
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

📍 Current AQI: {round(current_aqi)}
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
                        precautions=precautions,
                        symptom_weighted_penalties=risk_explanation.get("symptom_weighted_penalties", {})
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


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR NEW FEATURES (Feature 3, 4, 8)
# ═══════════════════════════════════════════════════════════════════════════════

async def check_and_send_medication_reminders(user: dict, current_aqi: int, tier: str) -> int:
    """
    Feature 3: Check if any medications should trigger reminders based on current AQI.
    Returns the number of reminders sent.
    """
    try:
        user_id = user["id"]
        medications = await asyncio.to_thread(db.get_user_medications, user_id)
        
        reminders_sent = 0
        for med in medications:
            aqi_trigger = med.get("aqi_trigger")
            if aqi_trigger and current_aqi >= aqi_trigger:
                # Check if reminder already sent recently (within 6 hours)
                recent_reminder = await asyncio.to_thread(
                    db.check_recent_medication_reminder, 
                    med["id"], 
                    hours=6
                )
                
                if not recent_reminder:
                    # Send medication reminder
                    success = await send_medication_reminder_notification(user, med, current_aqi)
                    if success:
                        reminders_sent += 1
                        logger.info(f"✓ Medication reminder sent for {user['name']}: {med['medication_name']}")
        
        return reminders_sent
        
    except Exception as exc:
        logger.error(f"Error checking medication reminders for user {user.get('name')}: {exc}")
        return 0


async def send_family_group_alerts(user: dict, tier: str, current_aqi: int, effective_aqi: int) -> int:
    """
    Feature 4: Send alerts to family group members when user is at high risk or critical.
    Returns the number of family members notified.
    """
    try:
        user_id = user["id"]
        user_name = user.get("name", "Family Member")
        
        # Get user's family groups
        family_groups = await asyncio.to_thread(db.get_user_family_groups, user_id)
        
        total_notified = 0
        for group in family_groups:
            if not group.get("emergency_mode"):
                continue  # Skip if emergency mode is disabled for this group
            
            group_id = group["id"]
            group_name = group["group_name"]
            
            # Get all members of this group
            members = await asyncio.to_thread(db.get_family_group_members, group_id)
            
            notifications_sent = 0
            for member in members:
                # Don't notify the user themselves
                if member["user_id"] == user_id:
                    continue
                
                if not member.get("notifications_enabled"):
                    continue
                
                # Send notification to this family member
                success = await send_family_member_notification(
                    member, 
                    user_name, 
                    tier, 
                    current_aqi, 
                    effective_aqi,
                    group_name
                )
                if success:
                    notifications_sent += 1
            
            # Log the family alert
            if notifications_sent > 0:
                alert_message = f"{user_name} is experiencing {tier.upper()} air quality conditions (AQI: {round(effective_aqi)})"
                await asyncio.to_thread(
                    db.log_family_alert,
                    group_id=group_id,
                    triggered_by_user=user_id,
                    alert_type="critical_aqi" if tier.lower() == "critical" else "high_aqi",
                    message=alert_message,
                    members_notified=notifications_sent
                )
                logger.info(f"✓ Family alert sent for {user_name} in group '{group_name}': {notifications_sent} members notified")
            
            total_notified += notifications_sent
        
        return total_notified
        
    except Exception as exc:
        logger.error(f"Error sending family alerts for user {user.get('name')}: {exc}")
        return 0


async def trigger_emergency_contact_alerts(user: dict, current_aqi: int) -> int:
    """
    Feature 8: Trigger emergency contact notifications for critical AQI events.
    Returns the number of emergency contacts notified.
    """
    try:
        user_id = user["id"]
        user_name = user.get("name", "Patient")
        
        # Get user's emergency contacts
        contacts = await asyncio.to_thread(db.get_user_emergency_contacts, user_id)
        
        notifications_sent = 0
        for contact in contacts:
            if not contact.get("notify_on_critical"):
                continue  # Skip if not configured for critical alerts
            
            # Send emergency notification
            success = await send_emergency_contact_notification(user, contact, current_aqi)
            if success:
                notifications_sent += 1
                logger.info(f"✓ Emergency alert sent to {contact['contact_name']} for {user_name}")
        
        return notifications_sent
        
    except Exception as exc:
        logger.error(f"Error triggering emergency notifications for user {user.get('name')}: {exc}")
        return 0


async def send_medication_reminder_notification(user: dict, medication: dict, current_aqi: int) -> bool:
    """Send medication reminder via WhatsApp."""
    try:
        from alerts import send_whatsapp
        
        phone = user.get("phone")
        if not phone:
            return False
        
        medication_name = medication["medication_name"]
        dosage = medication["dosage"]
        user_name = user.get("name", "Patient")
        medication_type = medication.get("medication_type", "medication")
        
        message = f"""💊 MEDICATION REMINDER - Pranarakshak

Hello {user_name}!

🚨 High AQI Alert: {current_aqi} (Your threshold: {medication['aqi_trigger']})

Please take your medication NOW:
📋 {medication_name}
💉 Dosage: {dosage}
🏥 Type: {medication_type.replace('_', ' ').title()}

This medication will help protect your respiratory health during poor air quality conditions.

⚠️ Important: Do not skip this dose even if you feel okay. Preventive medication is crucial during high pollution.

Take care and stay safe! 🌬️
- Pranarakshak Health Assistant"""
        
        status, msg_id = send_whatsapp(phone, message)
        
        # Log the reminder
        if status == "sent":
            await asyncio.to_thread(
                db.log_medication_reminder,
                medication_id=medication["id"],
                user_id=user["id"],
                reminder_type="aqi_triggered",
                aqi_at_time=current_aqi,
                message_sent=message,
                channel="whatsapp",
                status="sent"
            )
        
        return status == "sent"
        
    except Exception as exc:
        logger.error(f"Error sending medication reminder: {exc}")
        return False


async def send_family_member_notification(member: dict, patient_name: str, tier: str, current_aqi: int, effective_aqi: int, group_name: str) -> bool:
    """Send notification to family group member."""
    try:
        from alerts import send_whatsapp
        
        member_name = member.get("name", "Family Member")
        phone = member.get("phone")
        
        if not phone:
            return False
        
        tier_emoji = "🚨" if tier.lower() == "critical" else "🟠"
        
        message = f"""👨‍👩‍👧‍👦 FAMILY ALERT - Pranarakshak

{tier_emoji} URGENT: {patient_name} needs your attention!

Your family member is experiencing {tier.upper()} air quality conditions:

📊 Current AQI: {round(current_aqi)}
🔴 Personal Risk Level: {round(effective_aqi)}
⚠️ Risk Tier: {tier.upper()}

👥 Family Group: {group_name}

🆘 What to do:
1. Call or message {patient_name} immediately
2. Ensure they are staying indoors
3. Check if they have taken their medications
4. Monitor for breathing difficulties
5. Be ready to assist if needed

This is an automated alert from your family health monitoring system.

💙 Pranarakshak - Family Health Guardian"""
        
        status, msg_id = send_whatsapp(phone, message)
        return status == "sent"
        
    except Exception as exc:
        logger.error(f"Error sending family notification: {exc}")
        return False


async def send_emergency_contact_notification(user: dict, contact: dict, current_aqi: int) -> bool:
    """Send emergency notification to emergency contact via WhatsApp and Email."""
    try:
        from alerts import send_whatsapp, send_email
        
        user_name = user.get("name", "Patient")
        contact_name = contact["contact_name"]
        relationship = contact["relationship"]
        condition = user.get("condition", "respiratory condition")
        severity = user.get("severity", "moderate")
        
        emergency_message = f"""🚨 EMERGENCY ALERT - Pranarakshak

⚠️ CRITICAL AIR QUALITY ALERT ⚠️

Patient: {user_name}
Your Relationship: {relationship.replace('_', ' ').title()}
Current AQI: {current_aqi} (CRITICAL LEVEL)

🔴 IMMEDIATE DANGER: {user_name} is experiencing CRITICAL air quality conditions that pose immediate health risks for their {condition.upper()} ({severity}).

🆘 URGENT ACTIONS REQUIRED:

1. 📞 Call {user_name} IMMEDIATELY
2. 🏠 Ensure they are indoors with windows/doors CLOSED
3. 💊 Verify they have taken rescue medications
4. 🌬️ Check if air purifier is running (if available)
5. 👁️ Monitor for these WARNING SIGNS:
   • Severe breathing difficulty
   • Chest pain or tightness
   • Bluish lips or face
   • Confusion or dizziness
   • Inability to speak in full sentences

⚠️ IF ANY WARNING SIGNS: Call emergency services (108/102) or rush to nearest hospital

This is an AUTOMATED EMERGENCY ALERT from Pranarakshak AI Health Monitoring System.

Emergency Contact: {contact_name}
Priority Level: {contact['priority']} (1=Highest)
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Stay alert and act fast! 🚨"""
        
        notifications_sent = False
        
        # Send WhatsApp if phone available
        if contact.get("phone"):
            status, msg_id = send_whatsapp(contact["phone"], emergency_message)
            if status == "sent":
                notifications_sent = True
                logger.info(f"Emergency WhatsApp sent to {contact_name} ({contact['phone']})")
        
        # Send Email if email available for redundancy
        if contact.get("email"):
            subject = f"🚨 EMERGENCY: Critical AQI Alert for {user_name}"
            html_message = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #fff3cd; border: 3px solid #dc3545;">
    <div style="background-color: #dc3545; color: white; padding: 15px; text-align: center; border-radius: 8px; margin-bottom: 20px;">
        <h1 style="margin: 0; font-size: 24px;">🚨 EMERGENCY ALERT 🚨</h1>
        <p style="margin: 5px 0 0 0; font-size: 14px;">Critical Air Quality Warning</p>
    </div>
    
    <div style="background-color: white; padding: 20px; border-radius: 8px; border: 2px solid #dc3545;">
        <pre style="white-space: pre-wrap; font-family: Arial, sans-serif; line-height: 1.6;">{emergency_message}</pre>
    </div>
    
    <div style="margin-top: 20px; padding: 15px; background-color: #f8d7da; border-radius: 8px; text-align: center;">
        <p style="margin: 0; color: #721c24; font-weight: bold;">This is an automated emergency notification</p>
        <p style="margin: 5px 0 0 0; color: #721c24; font-size: 12px;">Pranarakshak AI Health Monitoring System</p>
    </div>
</body>
</html>
"""
            status, msg_id = send_email(contact["email"], subject, html_message)
            if status == "sent":
                notifications_sent = True
                logger.info(f"Emergency email sent to {contact_name} ({contact['email']})")
        
        return notifications_sent
        
    except Exception as exc:
        logger.error(f"Error sending emergency notification: {exc}")
        return False
