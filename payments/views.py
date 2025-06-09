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
            is_active=False  # User must activate via email
        )

        activation_url = generate_activation_link(user, request)

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Welcome to CRISP AI</title>
        <style>
            body {{
            margin: 0; padding: 0;
            background: linear-gradient(to bottom right, #f2f6fc, #e8f0fe);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #333;
            }}
            .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.05); }}
            .header {{ background-color: #002B5B; padding: 20px; text-align: center; }}
            .header img {{ max-width: 180px; }}
            .content {{ padding: 30px; }}
            h1 {{ color: #002B5B; font-size: 24px; }}
            p {{ font-size: 16px; line-height: 1.6; }}
            .footer {{ text-align: center; padding: 20px; font-size: 13px; color: #777; }}
        </style>
        </head>
        <body>
        <div class="container">
            <div class="header">
            <img src="https://crispai.crispvision.org/media/crisp-logo.png" alt="CRISP AI Logo">
            </div>
            <div class="content">
            <h1>Hi {data['first_name']}, Welcome to CRISP AI 🎉</h1>
            <p>We’re excited to have you on board!</p>
            <p>Click the button below to activate your account:</p>
            <p><a href="{activation_url}" style="background-color:#002B5B;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">Activate Account</a></p>
            <p>– The CRISP AI Team</p>
            </div>
            <div class="footer">
            © {data['first_name'].capitalize()}, CRISP AI – Powered by CrispVision<br>
            <a href="https://crispai.crispvision.org" style="color:#002B5B;">Visit our website</a>
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
             success_url="http://localhost:8080/dashboard?status=success&session_id={CHECKOUT_SESSION_ID}",
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
                  <h1>✅ Your account has been successfully activated!</h1>
                  <p>You can now return to <a href="https://crispai.crispvision.org">CRISP AI</a> and log in.</p>
                </div>
              </body>
            </html>
        """)
    else:
        return HttpResponse("Invalid or expired activation link.", status=400)
