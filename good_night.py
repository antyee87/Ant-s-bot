import discord
import datetime
from discord.ext import tasks,commands

tz=datetime.timezone(datetime.timedelta(hours=8))
everyday_time = datetime.time(hour=0,minute=0,tzinfo=tz)
class GoodNight(commands.Cog):
    def __init__(self,bot:commands.bot):
        self.bot=bot
        self.everyday.start()
    
    @tasks.loop(time=everyday_time)
    async def everyday(self):
        channel_id = 1262855170841382997
        channel = self.bot.get_channel(channel_id)
        embed = discord.Embed(
            title = "🛏 晚安！瑪卡巴卡！",
            description = f"🕛 現在時間 {datetime.date.today()} 00:00",
            color = discord.Color.orange()
        )
        await channel.send(embed = embed)
        
async def setup(bot:commands.Bot):
    await bot.add_cog(GoodNight(bot))