import discord
from discord.ext import tasks, commands
from discord import app_commands
import os
from pytubefix import YouTube
from pytubefix import Playlist
from pytubefix.cli import on_progress
from pytubefix.exceptions import VideoUnavailable, RegexMatchError
from collections import deque
import asyncio
import re
import time

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vc = None
        self.playlist = deque()
        self.play_next.start()
        self.video_regex = re.compile(
            r'(https?://)?(www\.)?((youtube\.com)|(youtu\.?be))/watch\?v=.+'
        )
        self.playlist_regex = re.compile(
            r'(https?://)?(www\.)?((youtube\.com)|(youtu\.?be))/playlist\?list=.+'
        )
        
        
        files = os.listdir("downloads")
        # 逐一删除文件
        for file in files:
            file_path = os.path.join("downloads", file)
            if os.path.isfile(file_path):
                os.remove(file_path)

    async def download(self, url, mode):
        if not os.path.exists("downloads"):
            os.makedirs("downloads")
        
        if self.playlist_regex.match(url): 
            pl = Playlist(url)
            for video in pl.videos:
                ys=video.streams.get_audio_only()
                filepath = await asyncio.to_thread(ys.download, "downloads")
                filename = os.path.basename(filepath)
                if mode == "append":
                    self.playlist.append(filename)
                elif mode == "appendleft":
                    self.playlist.append(filename)
        
        elif self.video_regex.match(url):
            yt = YouTube(url, on_progress_callback=on_progress)
            ys = yt.streams.get_audio_only()
            filepath = await asyncio.to_thread(ys.download, "downloads")
            filename = os.path.basename(filepath)
            if mode == "append":
                self.playlist.append(filename)
            elif mode == "appendleft":
                self.playlist.appendleft(filename)

    def play_audio(self, vc, filepath):
        print(f"Attempting to play audio from file: {filepath}")
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File {filepath} not found.")
        
        if self.vc.is_playing():
            self.vc.stop()

        vc.play(discord.FFmpegPCMAudio(source=filepath))

    def is_valid_youtube_url(self, url: str) -> bool:
        try:
            if self.video_regex.match(url) or self.playlist_regex.match(url):
                return True
            else:
                return False
        except (VideoUnavailable, RegexMatchError):
            return False

    @app_commands.command(name="play", description="將機器人加入頻道並播放當前音樂")
    async def play(self, interaction: discord.Interaction, url: str):
        if self.is_valid_youtube_url(url):
            asyncio.create_task(self.download(url, "appendleft"))
        else:
            await interaction.response.send_message("Invalid YouTube URL or the video is not available.")
        channel = interaction.user.voice.channel

        await interaction.response.send_message(f"播放音樂\n{url}")
        if isinstance(channel, discord.VoiceChannel):
            if interaction.guild.voice_client:  # 或者使用 guild.voice_channels 也可以
                if interaction.guild.voice_client.channel == channel:
                    self.play_audio(self.vc, f"downloads/{self.playlist[0]}")
            else:
                self.vc = await channel.connect()
                self.play_audio(self.vc, f"downloads/{self.playlist[0]}")
        else:
            await interaction.response.send_message("You need to be in a voice channel to use this command.")

    @app_commands.command(name="disconnect", description="離開頻道")
    async def disconnect(self, interaction: discord.Interaction):
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()
            await interaction.response.send_message("機器人已離開頻道QwQ")
        else:
            await interaction.response.send_message("Not connected to a voice channel.")

    @app_commands.command(name="skip", description="跳過當前音樂")
    async def skip(self, interaction: discord.Interaction):
        if self.vc and self.vc.is_playing():
            name,ext=os.path.splitext(self.playlist[0])
            await interaction.response.send_message(f"已跳過音樂{name}")
            self.vc.stop()
        else:
            await interaction.response.send_message("No music is currently playing.")

    @app_commands.command(name="add", description="將youtube音樂(播放清單)加入播放清單")
    async def add(self, interaction: discord.Interaction, url: str):
        if self.is_valid_youtube_url(url):
            asyncio.create_task(self.download(url, "append"))
            await interaction.response.send_message(f"加入音樂\n{url}")
        else:
            await interaction.response.send_message("Invalid YouTube URL or the video is not available.")
    
    @app_commands.command(name="list", description="顯示播放清單")
    async def list(self, interaction: discord.Interaction, page: int):
        embed = discord.Embed(title="播放清單", description=f"第 {page} 頁", color=0x0000ff)
        show_list = []
        for a in range((page - 1) * 10, page * 10):
            if a < len(self.playlist):
                name,ext=os.path.splitext(self.playlist[a])
                show_list.append(f"{a+1}. {name}")
            else:
                break

        for item in show_list:
            embed.add_field(name=item, value="", inline=False)

        await interaction.response.send_message(embed=embed)

    @tasks.loop(seconds=1)
    async def play_next(self):
        try:
            if self.vc and not self.vc.is_playing():
                if self.playlist:
                    file_to_remove = self.playlist[0]
                    self.playlist.popleft()
                    if not file_to_remove in self.playlist:
                        os.remove(f"downloads/{file_to_remove}")
                        print(f"Removed {file_to_remove}")
                    # 检查是否还有下一首歌曲需要播放
                    if self.playlist:
                        self.play_audio(self.vc, f"downloads/{self.playlist[0]}")
        except Exception as e:
            print(f"Error in play_next loop: {e}")
    @app_commands.command(name="vote_skip",description="發起後20秒內音樂頻道有超過1/4使用者同意且同意人數大於反對人數就跳過音樂")
    async def vote_skip(self,interaction:discord.Interaction):
        self.start_time = time.time()
        if self.vc.channel and self.vc.is_playing():
            self.members = len(interaction.user.voice.channel.members)
            self.voted_id=[]
            self.vote=0
            self.agree=0
            self.disagree=0
            
            view = discord.ui.View()
            # 使用 class 方式宣告 Button
            agree_button = discord.ui.Button(
                label = "同意跳過",
                style = discord.ButtonStyle.blurple
            )
            # Button 連接回呼函式
            agree_button.callback = self.vote_agree
            
            disagree_button = discord.ui.Button(
                label = "不同意跳過",
                style = discord.ButtonStyle.blurple
            )
            # Button 連接回呼函式
            disagree_button.callback = self.vote_disagree
            # 將 Button 添加到 View 中
            view.add_item(agree_button)
            view.add_item(disagree_button)
            await interaction.response.send_message(view = view) 
            self.bot.loop.create_task(self.view_remove(interaction))   
        else:
            await interaction.response.send_message("You need to be in a voice channel and play music to use this command.")   
        
    async def vote_agree(self,interaction: discord.Interaction):
        await interaction.response.send_message(f"等待中！還有{int(20-(time.time()-self.start_time))}秒", ephemeral=True)
        if not interaction.user.id in self.voted_id:
            self.voted_id.append(interaction.user.id)
            self.vote+=1
            self.agree+=1
    async def vote_disagree(self,interaction: discord.Interaction):
        await interaction.response.send_message(f"等待中！還有{int(20-(time.time()-self.start_time))}秒", ephemeral=True)
        if not interaction.user.id in self.voted_id:
            self.voted_id.append(interaction.user.id)
            self.vote+=1
            self.disagree+=1
    async def view_remove(self,interaction:discord.Interaction):
        await asyncio.sleep(20)  # 等待 20 秒
        await interaction.channel.send(f"{self.vote}人投票 {self.agree}人同意跳過  {self.disagree}人不同意跳過")
        if self.vote/self.members>=0.25:
            if self.agree > self.disagree:
                await interaction.channel.send("跳過此首")
                name,ext=os.path.splitext(self.playlist[0])
                await interaction.channel.send(f"已跳過音樂{name}")
                self.vc.stop()
                return
        await interaction.channel.send("繼續收聽")

            
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))