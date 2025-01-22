import logging
from datetime import datetime
from typing import Optional
import asyncio
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import Message, Update
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import TELEGRAM_TOKEN, OPEN_WEATHER_API_TOKEN
from open_weather_api import fetch_city_temperature

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


class CommandLoggerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        if event.message and event.message.text.startswith("/"):
            user = event.message.from_user
            command = event.message.text
            logging.info(f"user id: {user.id}, user name: {user.full_name}, command: {command}")
        return await handler(event, data)


dp.update.middleware(CommandLoggerMiddleware())

users = {}


def get_current_day() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class WaterLog:
    def __init__(self, amount: int):
        self.amount = amount


class CalorieLog:
    def __init__(self, food: str, amount: int):
        self.food = food
        self.amount = amount


class WorkoutLog:
    def __init__(self, workout: str, duration: int):
        self.workout = workout
        self.duration = duration


class DailyLog:
    def __init__(self, day: str, temperature: float, weight: int, height: int, age: int, activity: int):
        self.day = day
        self.temperature = temperature
        self.weight = weight
        self.height = height
        self.age = age
        self.activity = activity
        self.water_logs: list[WaterLog] = []
        self.calorie_logs: list[CalorieLog] = []
        self.workout_logs: list[WorkoutLog] = []

    def log_water(self, amount: int):
        self.water_logs.append(WaterLog(amount))

    def log_calories(self, food: str, amount: int):
        self.calorie_logs.append(CalorieLog(food, amount))

    def log_workout(self, workout: str, duration: int):
        self.workout_logs.append(WorkoutLog(workout, duration))

    def get_water(self):
        return sum([water_log.amount for water_log in self.water_logs])

    def get_water_goal(self):
        water_goal = self.weight * 30

        # if the temperature is above 25 degrees, add 500 ml
        if self.temperature > 25:
            water_goal = water_goal + 500

        # add 500 ml for every 30 minutes of activity
        water_goal = water_goal + self.activity // 30 * 500

        # workout
        water_goal = water_goal + self.get_water_added_by_workout()

        return water_goal

    def get_water_added_by_workout(self):
        # add 200 ml for every 30 minutes of workout
        return sum([workout_log.duration for workout_log in self.workout_logs]) // 30 * 200

    def get_calorie(self):
        return sum([calorie_log.amount for calorie_log in self.calorie_logs])

    def get_calorie_burned(self):
        # each minute of workout burns 10 calories
        return sum([workout_log.duration for workout_log in self.workout_logs]) * 10

    def get_calorie_goal(self):
        calorie_goal = 10 * self.weight + 6.75 * self.height - 5 * self.age + 5

        # workout
        calorie_goal = calorie_goal + self.get_calorie_added_by_workout()

        return calorie_goal

    def get_calorie_added_by_workout(self):
        # add 200 calories for every 60 minutes of workout
        return sum([workout_log.duration for workout_log in self.workout_logs]) // 60 * 200


class User:
    def __init__(self, name: str, weight: int, height: int, age: int, activity: int, city: str):
        self.name = name
        self.weight = weight
        self.height = height
        self.age = age
        self.activity = activity
        self.city = city
        self.logs = {}

    async def get_log(self) -> DailyLog:
        day = get_current_day()

        daily_log = self.logs.get(day)

        if daily_log is None:
            # fetch temperature for the city
            temperature = await fetch_city_temperature(self.city)

            daily_log = DailyLog(
                day=day,
                temperature=temperature,
                weight=self.weight,
                height=self.height,
                age=self.age,
                activity=self.activity
            )

            self.logs[day] = daily_log

        return daily_log


async def get_int_text(message: Message, min_val=1, max_val=1_000_000) -> Optional[int]:
    try:
        value = int(message.text)

        if value <= min_val or value >= max_val:
            raise ValueError()

        return value

    except ValueError:
        await message.answer(f"Please enter a correct number between {min_val} and {max_val}:")
        return None


async def get_str_text(message: Message, min_len=1, max_len=50) -> Optional[str]:
    try:
        value = str(message.text)

        if len(value) < min_len or len(value) > max_len:
            raise ValueError()

        return value

    except ValueError:
        await message.answer("Please enter a correct value:")
        return None


COMMANDS_TEXT = """You now have access to the following commands:
📋 <b>/profile</b> — Show your profile
🛠 <b>/set_profile</b> — Update your profile
💧 <b>/log_water</b> — Log your water intake
🍎 <b>/log_food</b> — Log your food intake
🏋️‍♂️ <b>/log_workout</b> — Log your workout
📈 <b>/current_progress</b> — Show your current progress
"""


async def get_user(message: Message) -> Optional[User]:
    user = users.get(message.from_user.id)

    if user is None:
        await message.answer("You haven't set your profile yet, use <b>/set_profile</b> command", parse_mode="HTML")
        return None

    return user


#
# /start
#

@dp.message(Command("start"))
async def handle_start(message: Message):
    user = message.from_user

    if user.id in users:
        reply = f"""
<b>Hello, {user.first_name}</b> 👋
I'm your personal fitness assistant

{COMMANDS_TEXT}
        """

    else:
        reply = f"""
<b>Hello, {user.first_name}</b> 👋
I'm your personal fitness assistant

To get started, set up your profile with <b>/set_profile</b>
        """

    await message.answer(reply, parse_mode="HTML")


#
# /profile
#

@dp.message(Command("profile"))
async def handle_profile(message: Message):
    user = await get_user(message)

    if user is None:
        return

    reply = f"""
🌟 Your Profile 🌟

<b>{user.name}, {user.age} years old, {user.city}</b>

📏 <b>Weight:</b> {user.weight} kg  
📐 <b>Height:</b> {user.height} cm  
🏃‍♂️ <b>Daily Activity:</b> {user.activity} minutes
"""

    await message.answer(reply, parse_mode="HTML")


#
# /set_profile
#

class ProfileState(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()


@dp.message(Command("set_profile"))
async def handle_set_profile(message: Message, state: FSMContext):
    await state.set_state(ProfileState.weight)
    await message.answer("Enter your <b>weight</b> (kg):", parse_mode="HTML")


@dp.message(ProfileState.weight)
async def handle_set_profile_weight(message: Message, state: FSMContext):
    weight = await get_int_text(message, min_val=10, max_val=500)
    if weight is None:
        return

    await state.update_data(weight=weight)

    await state.set_state(ProfileState.height)
    await message.answer("Enter your <b>height</b> (cm):", parse_mode="HTML")


@dp.message(ProfileState.height)
async def handle_set_profile_height(message: Message, state: FSMContext):
    height = await get_int_text(message, min_val=10, max_val=260)
    if height is None:
        return

    await state.update_data(height=height)

    await state.set_state(ProfileState.age)
    await message.answer("Enter your <b>age</b>:", parse_mode="HTML")


@dp.message(ProfileState.age)
async def handle_set_profile_age(message: Message, state: FSMContext):
    age = await get_int_text(message, min_val=18, max_val=150)
    if age is None:
        return

    await state.update_data(age=age)

    await state.set_state(ProfileState.activity)
    await message.answer("Enter your <b>daily activity</b> (minutes):", parse_mode="HTML")


@dp.message(ProfileState.activity)
async def handle_set_profile_activity(message: Message, state: FSMContext):
    activity = await get_int_text(message, min_val=1, max_val=1440)
    if activity is None:
        return

    await state.update_data(activity=activity)

    await state.set_state(ProfileState.city)
    await message.answer("Enter your <b>city</b>:", parse_mode="HTML")


@dp.message(ProfileState.city)
async def handle_set_profile_city(message: Message, state: FSMContext):
    city = await get_str_text(message)
    if city is None:
        return

    # Trying to get weather data for the city
    if await fetch_city_temperature(city) is None:
        await message.answer("Please enter a correct city name:")

        return

    await state.update_data(city=city)

    data = await state.get_data()

    users[message.from_user.id] = User(
        name=message.from_user.full_name,
        weight=data["weight"],
        height=data["height"],
        age=data["age"],
        activity=data["activity"],
        city=data["city"]
    )

    reply = f"""
🎉 <b>Profile Successfully Set!</b> 🎉

{COMMANDS_TEXT}
    """

    await message.answer(reply, parse_mode="HTML")
    await state.clear()


#
# /log_water
#

class LogWaterState(StatesGroup):
    amount = State()


@dp.message(Command("log_water"))
async def handle_log_water(message: Message, state: FSMContext):
    user = await get_user(message)
    if user is None:
        return

    await state.set_state(LogWaterState.amount)
    await message.answer("Enter the amount of water you drank (ml):")


@dp.message(LogWaterState.amount)
async def handle_log_water_amount(message: Message, state: FSMContext):
    user = await get_user(message)
    if user is None:
        return

    amount = await get_int_text(message, min_val=1, max_val=10_000)
    if amount is None:
        return

    log = await user.get_log()
    log.log_water(amount)

    reply = f"""
💧 <b>Water Intake Logged!</b> 💧

Water consumed: {log.get_water()} of {log.get_water_goal()} ml
"""

    await message.answer(reply, parse_mode="HTML")
    await state.clear()


#
# /log_food
#

class LogFoodState(StatesGroup):
    food = State()
    amount = State()


@dp.message(Command("log_food"))
async def handle_log_food(message: Message, state: FSMContext):
    user = await get_user(message)
    if user is None:
        return

    await state.set_state(LogFoodState.food)
    await message.answer("Enter the food you ate:")


@dp.message(LogFoodState.food)
async def handle_log_food_food(message: Message, state: FSMContext):
    user = await get_user(message)
    if user is None:
        return

    food = await get_str_text(message)
    if food is None:
        return

    await state.update_data(food=food)

    await state.set_state(LogFoodState.amount)
    await message.answer("Enter the amount of food you ate (calories):")


@dp.message(LogFoodState.amount)
async def handle_log_food_amount(message: Message, state: FSMContext):
    user = await get_user(message)
    if user is None:
        return

    amount = await get_int_text(message, min_val=1, max_val=10_000)
    if amount is None:
        return

    await state.update_data(amount=amount)

    log = await user.get_log()
    data = await state.get_data()

    log.log_calories(data["food"], data["amount"])

    reply = f"""
🍎 <b>Food Intake Logged!</b> 🍎

Calories consumed: {log.get_calorie()} of {log.get_calorie_goal()} calories
"""

    await message.answer(reply, parse_mode="HTML")
    await state.clear()


#
# /log_workout
#

class LogWorkoutState(StatesGroup):
    workout = State()
    duration = State()


@dp.message(Command("log_workout"))
async def handle_log_workout(message: Message, state: FSMContext):
    user = await get_user(message)
    if user is None:
        return

    await state.set_state(LogWorkoutState.workout)
    await message.answer("Enter the workout you did:")


@dp.message(LogWorkoutState.workout)
async def handle_log_workout_workout(message: Message, state: FSMContext):
    user = await get_user(message)
    if user is None:
        return

    workout = await get_str_text(message)
    if workout is None:
        return

    await state.update_data(workout=workout)

    await state.set_state(LogWorkoutState.duration)
    await message.answer("Enter the duration of the workout (minutes):")


@dp.message(LogWorkoutState.duration)
async def handle_log_workout_duration(message: Message, state: FSMContext):
    user = await get_user(message)
    if user is None:
        return

    duration = await get_int_text(message, min_val=1, max_val=1_440)
    if duration is None:
        return

    await state.update_data(duration=duration)

    log = await user.get_log()
    data = await state.get_data()

    log.log_workout(data["workout"], data["duration"])

    if log.get_water_added_by_workout() > 0:
        reply = f"""
🏋️‍♂️ <b>Workout Logged!</b> 🏋️‍♂️

Note: Drink additional {log.get_water_added_by_workout()} ml of water today
"""
    else:
        reply = f"""
🏋️‍♂️ <b>Workout Logged!</b> 🏋️‍♂️
"""

    await message.answer(reply, parse_mode="HTML")
    await state.clear()


#
# /current_progress
#

@dp.message(Command("current_progress"))
async def handle_current_progress(message: Message):
    user = await get_user(message)
    if user is None:
        return

    log = await user.get_log()

    temp_text = f"Today's temperature in {user.city} is {log.temperature}°C"

    if log.temperature > 25:
        temp_text += "\nYou should drink more water today"

    reply = f"""
📈 <b>Your Current Progress</b> 📈
{temp_text}

💧 <b>Water:</b>
Water consumed: {log.get_water()} of {log.get_water_goal()} ml
Water added by workout: {log.get_water_added_by_workout()} ml

🍎 <b>Calories:</b>
Calories consumed: {log.get_calorie()} of {log.get_calorie_goal()} calories
Calories burned: {log.get_calorie_burned()} calories
Calories added by workout: {log.get_calorie_added_by_workout()} calories

🏋️‍♂️ <b>Workout:</b>
Workouts: {len(log.workout_logs)}
Total duration: {sum([workout_log.duration for workout_log in log.workout_logs])} minutes
"""

    await message.answer(reply, parse_mode="HTML")


#
# Handle all other messages
#

@dp.message()
async def handle_other_messages(message: Message):
    reply = f"""
Unknown command, consider using <b>/start</b>
    """

    await message.answer(reply, parse_mode="HTML")


async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
