import stripe
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from django.core.mail import EmailMultiAlternatives
from .models import User, Tool, Subscription
from .serializers import LoginSerializer,ToolSerializer
from .utils import generate_activation_link
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.urls import reverse

stripe.api_key = settings.STRIPE_SECRET_KEY

@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    data = request.data
    required_fields = ["first_name", "last_name", "email", "phone", "password", "repeat_password"]

    for field in required_fields:
        if not data.get(field):
            return Response({"error": f"{field} is required"}, status=400)

    if data["password"] != data["repeat_password"]:
        return Response({"error": "Passwords do not match"}, status=400)

    try:
        user = User.objects.create(
            username=data["email"],
            email=data["email"],
            password=make_password(data["password"]),
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data["phone"],
            is_active=False 
        )

        activation_url = generate_activation_link(user, request)

        html_body = f"""
        <!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Welcome to CRISPAI</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: #f8fafc;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            overflow: hidden;
        }}
        .banner {{
            background: #f1f5f9;
            padding: 30px 20px;
            text-align: center;
            border-bottom: 1px solid #e2e8f0;
        }}
        .banner img {{
            max-width: 180px;
            height: auto;
        }}
        .content {{
            padding: 40px 30px;
            text-align: center;
        }}
        h1 {{
            color: #002B5B;
            font-size: 26px;
            margin-top: 0;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        p {{
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 24px;
            color: #4a5568;
        }}
        .button-container {{
            margin: 32px 0;
        }}
        .activate-button {{
            background-color: #002B5B;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            display: inline-block;
            font-size: 16px;
        }}
        .footer {{
            text-align: center;
            padding: 24px;
            font-size: 13px;
            color: #718096;
            border-top: 1px solid #edf2f7;
            background: #f8fafc;
        }}
        .footer a {{
            color: #002B5B;
            text-decoration: none;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="banner">
            <img src="https://crispai.crispvision.org/media/crisp-logo.png" alt="CRISP AI Logo">
        </div>
        <div class="content">
            <h1>Hi {data['first_name']}, Welcome to CrispAI</h1>
            <p>We're excited to have you on board!</p>
            <p>Click the button below to activate your account:</p>
            <div class="button-container">
                <a href="{activation_url}" class="activate-button">Activate Account</a>
            </div>
            <p>If you didn't request this, please ignore this email.</p>
        </div>
        <div class="footer">
            © 2024 CrispAI. All rights reserved.<br>
            <a href="https://www.crispai.ca/">Visit our website</a> | <a href="mailto:support@crispai.ca">Contact Support</a>
        </div>
    </div>
</body>
</html>
        """


        subject = "🎉 Welcome to CRISP AI – Let’s Build the Future Together!"
        text_body = f"Hi {data['first_name']},\n\nClick the link below to activate your account:\n\n{activation_url}"
        from_email = settings.DEFAULT_FROM_EMAIL
        msg = EmailMultiAlternatives(subject, text_body, from_email, [user.email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()

        return Response({"detail": "Registration successful. Please check your email to activate your account."})
    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(["GET"])
@permission_classes([AllowAny])
def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return Response({"detail": "Account activated successfully. You can now log in."})
    else:
        return Response({"error": "Activation link is invalid or expired."}, status=400)

@api_view(['POST'])
def login(request):
    email = request.data.get("email")
    password = request.data.get("password")

    user = authenticate(request, username=email, password=password)

    if user is not None:
        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role if hasattr(user, 'role') else '',
            }
        })
    else:
        return Response({"detail": "Invalid credentials"}, status=401)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_subscription(request):
    user = request.user
    active_subs = Subscription.objects.filter(user=user, status="active")
    tools = [sub.tool.id for sub in active_subs]

    return Response({
        "has_access": len(tools) > 0,
        "tools": tools
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agent_gateway(request):
    user = request.user
    if user.role == "agent":
        return redirect("https://crispai.crispvision.org/agent-dashboard")
    return Response({"detail": "Unauthorized"}, status=403)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout(request):
    user = request.user
    tool_input = request.data.get("tool_id")

    if not tool_input:
        return Response({"detail": "Missing tool_id"}, status=400)

    try:
        # Check if the tool_input is a digit (numeric ID), otherwise use name
        if str(tool_input).isdigit():
            tool = Tool.objects.get(id=int(tool_input))
        else:
            tool = Tool.objects.get(name__iexact=tool_input)

        if Subscription.objects.filter(user=user, tool=tool, status="active").exists():
            return Response({"detail": "Already subscribed"}, status=400)

        session = stripe.checkout.Session.create(
            customer_email=user.email,
            payment_method_types=["card"],
            line_items=[{
                'price': tool.price_id,
                'quantity': 1
            }],
            mode='subscription',
            subscription_data={"trial_period_days": 7},
             success_url="https://marketplace.crispai.ca/?status=success&session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:8080/cancel",
            metadata={"tool_id": str(tool.id)}
        )
        return Response({"checkout_url": session.url})

    except Tool.DoesNotExist:
        return Response({"detail": "Tool not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email")
        tool_id = session.get("metadata", {}).get("tool_id")

        try:
            user = User.objects.get(email=email)
            tool = Tool.objects.get(id=tool_id)
            Subscription.objects.create(
                user=user,
                tool=tool,
                status="active",
                email=email
            )
        except Exception:
            return HttpResponse(status=400)

    return HttpResponse(status=200)


@api_view(["GET"])
@permission_classes([AllowAny])
def list_tools(request):
    tools = Tool.objects.all()
    serializer = ToolSerializer(tools, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return HttpResponse("Invalid activation link", status=400)

    if default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return HttpResponse("""
            <html>
              <head>
                <title>Account Activated</title>
                <style>
                  body { font-family: 'Segoe UI', sans-serif; text-align: center; background: #f5f7fb; padding: 60px; }
                  .box { background: white; display: inline-block; padding: 40px 30px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }
                  h1 { color: #2ecc71; }
                  a { color: #002B5B; text-decoration: none; font-weight: bold; }
                </style>
              </head>
              <body>
                <div class="box">
                  <h1>Your account has been successfully activated!</h1>
                  <p>You can now return to <a href="https://crispai.crispvision.org">CRISP AI</a> and log in.</p>
                </div>
              </body>
            </html>
        """)
    else:
        return HttpResponse("Invalid or expired activation link.", status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_subscription(request):
    user = request.user
    tool_id = request.data.get("tool_id")
    
    if not tool_id:
        return Response({"detail": "tool_id is required"}, status=400)
    
    try:
        # Find the active subscription
        subscription = Subscription.objects.get(
            user=user,
            tool_id=tool_id,
            status="active"
        )
        
        # Update the subscription status to canceled
        subscription.status = "canceled"
        subscription.save()
        
        return Response({"detail": "Subscription canceled successfully"})
        
    except Subscription.DoesNotExist:
        return Response({"detail": "Active subscription not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscriptions(request):
    user = request.user
    subscriptions = Subscription.objects.filter(user=user)
    
    data = [{
        "id": sub.id,
        "tool": sub.tool.name,
        "tool_id": sub.tool.id,
        "status": sub.status,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at
    } for sub in subscriptions]
    
    return Response(data)