import discord
from discord.ext import commands
from discord import app_commands
import random

class Test(commands.Cog):
    def __init__(self,bot:commands.bot):     
        self.bot=bot
        self.guess={}
        self.nAnB={}

        
    def nAnB_number_generate(self):
        nAnB_number=[-1,-1,-1,-1]
        for a in range (4):
            while(True):
                nAnB_number[a]=random.randint(0,9)
                flag=True
                for b in range(a):
                    if(nAnB_number[b]==nAnB_number[a]):
                        flag=False
                        break
                if flag:
                    break
        return nAnB_number
         
    @app_commands.command(name="roll",description="roll a dice")
    async def roll(self,interaction:discord.Interaction):
        await interaction.response.send_message(random.randint(1,6))
    
    @app_commands.command(name="guess",description="guessed number between 1 to 100")
    async def guess(self,interaction:discord.Interaction,player_guess:int):
        guild_id=interaction.guild_id
        if not guild_id in self.guess:
            self.guess[guild_id]={
                "number":random.randint(1,100),
                "count":0               
            }
        self.guess[guild_id]["count"]+=1
        await interaction.response.send_message(f"{interaction.user} guess {player_guess}")
        if player_guess == self.guess[guild_id]["number"]:
            await interaction.channel.send("congratulation")
            await interaction.channel.send(f"you guess {self.guess[guild_id]["count"]} times")
            await interaction.channel.send("guessed number is reset")
            self.guess[guild_id]["number"]=random.randint(1,100)
            self.guess[guild_id]["count"]=0
        elif player_guess < self.guess[guild_id]["number"]:
            await interaction.channel.send("guessed number is bigger")
        elif player_guess > self.guess[guild_id]["number"]:
            await interaction.channel.send("guessed number is smaller")
    @app_commands.command(name="nanb",description="幾A幾B")
    async def nAnB(self,interaction:discord.Interaction,player_guess:str):
        guild_id=interaction.guild_id
        if player_guess.isdigit():
            if not guild_id in self.nAnB:
                self.nAnB[guild_id] = {
                    "count": 0,
                    "number": self.nAnB_number_generate()
                }
            int_player_guess=int(player_guess)
            if int_player_guess>=0 and int_player_guess<=9999:
                await interaction.response.send_message(f"猜測{player_guess}")
                player_guess_arr=[-1,-1,-1,-1]
                for i in range(3,-1,-1):
                    player_guess_copy=int_player_guess
                    player_guess_arr[3-i]=int(player_guess_copy/pow(10,i))
                    int_player_guess%=pow(10,i)
                self.nAnB[guild_id]["count"]+=1
                check_list=["N" for i in range(4)]
                for i in range(4):
                    if player_guess_arr[i]==self.nAnB[guild_id]["number"][i]:
                        check_list[i]="A"
                for a in range(4):
                    if check_list[a]=="A":
                        continue
                    else:
                        for b in range(4):
                            if self.nAnB[guild_id]["number"][a]==player_guess_arr[b]:
                                check_list[a]="B"
                                break
                A_count=0
                B_count=0
                for i in range(4):
                    if check_list[i]=="A":
                        A_count+=1
                    elif check_list[i]=="B":
                        B_count+=1
                await interaction.channel.send(f"{A_count}A{B_count}B")
                if A_count==4:
                    await interaction.channel.send(f"遊戲勝利 猜了{self.nAnB[guild_id]["count"]}次")
                    self.nAnB[guild_id]["number"]=self.nAnB_number_generate()
                    self.nAnB[guild_id]["count"]=0
                    await interaction.channel.send(f"數字刷新")
            else:
                await interaction.response.send_message("無效輸入")
        else:
            await interaction.response.send_message("無效輸入")
    @app_commands.command(name="nanb_giveup",description="我放棄猜幾A幾B")
    async def nAnB_giveup(self,interaction:discord.Interaction):
        guild_id=interaction.guild_id
        if not guild_id in self.nAnB:
            await interaction.response.send_message("你根本還沒開始猜= =")
        else:
            await interaction.response.send_message(f"答案:{self.nAnB[guild_id]["number"]}")
            
        
async def setup(bot:commands.bot):
    await bot.add_cog(Test(bot))