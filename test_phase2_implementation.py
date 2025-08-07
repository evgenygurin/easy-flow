#!/usr/bin/env python3
"""Test script for Phase 2 messaging platform implementation."""

import asyncio
from datetime import datetime
from typing import Any

# Test imports
try:
    from app.adapters.messaging.whatsapp import WhatsAppAdapter
    from app.adapters.messaging.vk import VKAdapter
    from app.adapters.messaging.viber import ViberAdapter
    from app.adapters.messaging.telegram import TelegramAdapter
    from app.services.template_service import TemplateService, MessageTemplate, TemplateCategory
    from app.models.messaging import UnifiedMessage, MessageType, MessageDirection
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)


def test_adapters_instantiation():
    """Test that all adapters can be instantiated."""
    print("\n🔧 Testing adapter instantiation...")
    
    try:
        # Test WhatsApp adapter
        whatsapp = WhatsAppAdapter(
            access_token="test_token",
            phone_number_id="test_phone_id", 
            business_account_id="test_business_id"
        )
        print("✅ WhatsApp adapter created")
        
        # Test VK adapter
        vk = VKAdapter(
            access_token="test_token",
            group_id="test_group_id"
        )
        print("✅ VK adapter created")
        
        # Test Viber adapter
        viber = ViberAdapter(
            auth_token="test_token",
            bot_name="Test Bot"
        )
        print("✅ Viber adapter created")
        
        # Test Telegram adapter (already working)
        telegram = TelegramAdapter(bot_token="test:token")
        print("✅ Telegram adapter created")
        
    except Exception as e:
        print(f"❌ Adapter instantiation error: {e}")
        return False
    
    return True


async def test_template_service():
    """Test template service functionality."""
    print("\n📝 Testing template service...")
    
    try:
        service = TemplateService()
        
        # Create a template
        template = await service.create_template(
            name="welcome_message",
            description="Welcome message template",
            category=TemplateCategory.UTILITY
        )
        print(f"✅ Template created: {template.id}")
        
        # List templates
        templates = await service.list_templates()
        print(f"✅ Listed {len(templates)} templates")
        
        # Get template stats
        stats = await service.get_template_stats(template.id)
        print(f"✅ Retrieved stats for template: {len(stats)} records")
        
    except Exception as e:
        print(f"❌ Template service error: {e}")
        return False
    
    return True


def test_unified_message():
    """Test unified message model."""
    print("\n💬 Testing unified message model...")
    
    try:
        message = UnifiedMessage(
            message_id="test_123",
            platform="whatsapp",
            platform_message_id="wa_123",
            user_id="user_123",
            chat_id="chat_123",
            message_type=MessageType.TEXT,
            direction=MessageDirection.INBOUND,
            text="Hello, world!"
        )
        print("✅ Unified message created")
        print(f"   - Platform: {message.platform}")
        print(f"   - Type: {message.message_type}")
        print(f"   - Text: {message.text}")
        
    except Exception as e:
        print(f"❌ Unified message error: {e}")
        return False
    
    return True


def test_platform_specific_features():
    """Test platform-specific features."""
    print("\n🌐 Testing platform-specific features...")
    
    try:
        # WhatsApp session window check
        whatsapp = WhatsAppAdapter("token", "phone", "business")
        within_window = whatsapp._is_within_session_window("test_chat")
        print(f"✅ WhatsApp session window check: {within_window}")
        
        # VK keyboard creation
        vk = VKAdapter("token", "group")
        from app.models.messaging import InlineKeyboard, InlineKeyboardButton
        
        keyboard = InlineKeyboard(buttons=[[
            InlineKeyboardButton(text="Test Button", callback_data="test")
        ]])
        vk_keyboard = vk._create_vk_keyboard(keyboard)
        print(f"✅ VK keyboard created: {vk_keyboard is not None}")
        
        # Viber keyboard creation
        viber = ViberAdapter("token", "Bot Name")
        viber_keyboard = viber._create_viber_keyboard(keyboard)
        print(f"✅ Viber keyboard created: {viber_keyboard is not None}")
        
    except Exception as e:
        print(f"❌ Platform-specific features error: {e}")
        return False
    
    return True


async def main():
    """Run all tests."""
    print("🚀 Starting Phase 2 implementation tests...\n")
    
    tests = [
        ("Adapter Instantiation", test_adapters_instantiation),
        ("Template Service", test_template_service),
        ("Unified Message", test_unified_message),
        ("Platform Features", test_platform_specific_features)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📊 Test Results Summary:")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:25} {status}")
    
    print("=" * 50)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Phase 2 implementation is ready.")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Review implementation.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)