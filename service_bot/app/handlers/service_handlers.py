from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from app.services.api_service import api_service
from app.keyboards.service_keyboards import (
    get_service_main_menu, 
    get_service_orders_list_keyboard, 
    get_service_order_actions_keyboard
)
from app.utils.formatting import format_service_order_details, format_service_orders_list

router = Router()

class ServiceAuthStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()

user_auth_data = {}

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    if message.from_user.id in user_auth_data:
        user_auth_data.pop(message.from_user.id)
    
    welcome_text = "👋 Добро пожаловать в бот для механиков СТО!\n\n📱 Пожалуйста, авторизуйтесь для продолжения."
    await message.answer(welcome_text)
    
    await message.answer("Введите ваш логин:")
    await state.set_state(ServiceAuthStates.waiting_for_login)

@router.message(ServiceAuthStates.waiting_for_login)
async def process_login(message: Message, state: FSMContext):
    """Обработчик ввода логина"""
    login = message.text.strip()
    
    user_auth_data[message.from_user.id] = {
        "login": login,
        "messages_to_delete": [message.message_id]
    }
    
    password_msg = await message.answer("Введите ваш пароль:")
    user_auth_data[message.from_user.id]["messages_to_delete"].append(password_msg.message_id)
    
    await state.set_state(ServiceAuthStates.waiting_for_password)

@router.message(ServiceAuthStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """Обработчик ввода пароля"""
    user_id = message.from_user.id
    password = message.text.strip()
    
    if user_id not in user_auth_data:
        await message.answer("Произошла ошибка. Пожалуйста, начните авторизацию заново с команды /start")
        return
    
    user_auth_data[user_id]["messages_to_delete"].append(message.message_id)
    login = user_auth_data[user_id]["login"]
    
    auth_successful = True
    
    if auth_successful:
        for msg_id in user_auth_data[user_id]["messages_to_delete"]:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения: {e}")
        
        await message.answer(
            f"✅ Вы успешно авторизованы как механик СТО, {login}!",
            reply_markup=get_service_main_menu()
        )
        await state.clear()
    else:
        await message.answer("❌ Неверный логин или пароль. Пожалуйста, попробуйте снова с команды /start")
        await state.clear()

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "🔍 <b>Справка по использованию бота для механиков СТО:</b>\n\n"
        "/start - Начать работу с ботом или вернуться в главное меню\n"
        "/help - Показать эту справку\n\n"
        "Используйте кнопки меню для навигации по функциям бота."
    )
    await message.answer(help_text)

@router.callback_query(F.data == "show_service_orders")
async def show_service_orders(callback: CallbackQuery):
    """Обработчик нажатия на кнопку показа всех заказов СТО"""
    await callback.answer()
    
    response = await api_service._make_request("GET", "/service-orders")
    
    if response.get("status") == 200 and "orders" in response.get("data", {}):
        orders = response["data"]["orders"]
        
        if not orders:
            await callback.message.answer("📋 Список заказов СТО пуст")
            return
        
        orders_text = format_service_orders_list(orders)
        
        keyboard = get_service_orders_list_keyboard(orders)
        
        await callback.message.answer(
            f"📋 <b>Список всех заказов СТО:</b>\n\n{orders_text}", 
            reply_markup=keyboard
        )
    else:
        error_msg = response.get("data", {}).get("message", "Неизвестная ошибка")
        await callback.message.answer(f"❌ Ошибка при получении списка заказов СТО: {error_msg}")

@router.callback_query(F.data.startswith("service_order_"))
async def show_service_order_details(callback: CallbackQuery):
    """Обработчик нажатия на кнопку конкретного заказа СТО"""
    order_number = callback.data.split("_")[2]
    await callback.answer()
    
    response = await api_service._make_request("GET", f"/service-orders/{order_number}")
    
    if response.get("status") == 200 and "order" in response.get("data", {}):
        order = response["data"]["order"]
        
        order_text = format_service_order_details(order)
        
        keyboard = get_service_order_actions_keyboard(order_number)
        
        await callback.message.answer(
            f"📝 <b>Детали заказа СТО #{order_number}:</b>\n\n{order_text}", 
            reply_markup=keyboard
        )
    else:
        error_msg = response.get("data", {}).get("message", "Неизвестная ошибка")
        await callback.message.answer(f"❌ Ошибка при получении деталей заказа СТО: {error_msg}")

@router.callback_query(F.data.startswith("service_accept_"))
async def accept_service_order(callback: CallbackQuery):
    """Обработчик нажатия на кнопку принятия заказа СТО"""
    order_number = callback.data.split("_")[2]
    await callback.answer("✅ Заказ принят")
    
    await callback.message.answer(f"✅ Заказ СТО #{order_number} успешно принят!")

@router.callback_query(F.data.startswith("service_reject_"))
async def reject_service_order(callback: CallbackQuery):
    """Обработчик нажатия на кнопку отклонения заказа СТО"""
    order_number = callback.data.split("_")[2]
    await callback.answer("❌ Заказ отклонен")
    
    await callback.message.answer(f"❌ Заказ СТО #{order_number} отклонен!")

@router.callback_query(F.data == "service_back_to_menu")
async def back_to_service_menu(callback: CallbackQuery):
    """Обработчик нажатия на кнопку возврата в главное меню"""
    await callback.answer()
    
    await callback.message.answer(
        "🏠 Главное меню", 
        reply_markup=get_service_main_menu()
    )

service_router = router
