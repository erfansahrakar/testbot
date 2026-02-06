"""
Enums برای مقادیر ثابت
✅ استفاده از Enum به جای String برای جلوگیری از Typo
"""
from enum import Enum


class OrderStatus(str, Enum):
    """وضعیت‌های مختلف سفارش"""
    PENDING = 'pending'
    WAITING_PAYMENT = 'waiting_payment'
    RECEIPT_SENT = 'receipt_sent'
    PAYMENT_CONFIRMED = 'payment_confirmed'
    CONFIRMED = 'confirmed'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    SHIPPED = 'shipped'


class DiscountType(str, Enum):
    """نوع تخفیف"""
    PERCENTAGE = 'percentage'
    FIXED = 'fixed'


class ShippingMethod(str, Enum):
    """روش‌های ارسال"""
    TERMINAL = 'terminal'
    BARBARI = 'barbari'
    TIPAX = 'tipax'
    CHAPAR = 'chapar'


class ErrorCategory(str, Enum):
    """دسته‌بندی خطاها"""
    DATABASE = "database"
    NETWORK = "network"
    TELEGRAM = "telegram"
    VALIDATION = "validation"
    BUSINESS = "business"
    UNKNOWN = "unknown"


class ErrorSeverity(str, Enum):
    """شدت خطا"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
