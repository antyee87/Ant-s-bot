import discord
from discord.ext import tasks, commands
from discord import app_commands
import os
import shutil
from pytubefix import YouTube
from pytubefix import Playlist
from pytubefix.cli import on_progress
from pytubefix.exceptions import VideoUnavailable, RegexMatchError
from collections import deque
import asyncio
import re
import time
from typing import Optional
import math
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.play_next.start()
        self.voice_clients = {}  # 存储每个服务器的语音客户端
        self.playlists = {}  # 存储每个服务器的播放列表
        self.vote_info = {}  # 存储每个服务器的投票信息
        self.video_regex = re.compile(
            r'(https?://)?(www\.)?((youtube\.com)|(youtu\.?be))/watch\?v=.+'
        )
        self.playlist_regex = re.compile(
            r'(https?://)?(www\.)?((youtube\.com)|(youtu\.?be))/playlist\?list=.+'
        )
        
        for filename in os.listdir("downloads"):
            file_path = os.path.join("downloads", filename)
            shutil.rmtree(file_path)  # 删除文件夹及其所有内容

    async def download(self, url, mode, guild_id):
        if not os.path.exists(f"downloads/{guild_id}"):
            os.makedirs(f"downloads/{guild_id}")
        
        if self.playlist_regex.match(url): 
            pl = Playlist(url)
            for video in pl.videos:
                ys = video.streams.get_audio_only()
                filepath = await asyncio.to_thread(ys.download, f"downloads/{guild_id}")
                filename, ext = os.path.splitext(os.path.basename(filepath))
                if mode == "append":
                    self.playlists[guild_id].append(filename)
                elif mode == "appendleft":
                    self.playlists[guild_id].append(filename)
        
        elif self.video_regex.match(url):
            yt = YouTube(url, on_progress_callback=on_progress)
            ys = yt.streams.get_audio_only()
            filepath = await asyncio.to_thread(ys.download, f"downloads/{guild_id}")
            filename, ext = os.path.splitext(os.path.basename(filepath))
            if mode == "append":
                self.playlists[guild_id].append(filename)
            elif mode == "appendleft":
                self.playlists[guild_id].appendleft(filename)

    def play_audio(self, vc, filepath):
        print(f"Attempting to play audio from file: {filepath}")
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File {filepath}.mp4 not found.")
        
        if vc.is_playing():
            vc.stop()

        vc.play(discord.FFmpegPCMAudio(source=filepath))

    def is_valid_youtube_url(self, url: str) -> bool:
        try:
            if self.video_regex.match(url) or self.playlist_regex.match(url):
                return True
            else:
                return False
        except (VideoUnavailable, RegexMatchError):
            return False

    @app_commands.command(name="play", description="將機器人加入頻道並插入播放音樂")
    async def play(self, interaction: discord.Interaction, url: Optional[str] = None):
        guild_id = interaction.guild.id
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            if guild_id not in self.playlists:
                self.playlists[guild_id] = deque()

            if url != None:
                await interaction.response.send_message(f"播放音樂\n{url}")

                if self.is_valid_youtube_url(url):
                    task1=asyncio.create_task(self.download(url, "appendleft", guild_id))
                else:
                    await interaction.response.send_message("Invalid YouTube URL or the video is not available.")
            else:
                await interaction.response.send_message(f"播放音樂\n{self.playlists[guild_id][0]}")

            if interaction.guild.voice_client:
                if interaction.guild.voice_client.channel != channel:
                    await interaction.guild.voice_client.move_to(channel)
            else:
                self.voice_clients[guild_id] = await channel.connect()
            task2 = asyncio.create_task(self.play_audio(self.voice_clients[guild_id], f"downloads/{guild_id}/{self.playlists[guild_id][0]}.mp4"))
            await task1
            await task2
        else:
            await interaction.response.send_message("You need to be in a voice channel to use this command.")

    @app_commands.command(name="leave", description="離開語音頻道(會保留播放清單)")
    async def leave(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            await self.voice_clients[guild_id].disconnect()
            await interaction.response.send_message("機器人已離開語音頻道QwQ")
        else:
            await interaction.response.send_message("Not connected to a voice channel.")

    @app_commands.command(name="skip", description="跳過當前音樂")
    async def skip(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_playing():
            await interaction.response.send_message(f"已跳過音樂{self.playlists[guild_id][0]}")
            self.voice_clients[guild_id].stop()
        else:
            await interaction.response.send_message("No music is currently playing.")

    @app_commands.command(name="add", description="將youtube音樂(播放清單)加入播放清單")
    async def add(self, interaction: discord.Interaction, url: str):
        guild_id = interaction.guild.id
        if guild_id not in self.playlists:
            self.playlists[guild_id] = deque()

        if self.is_valid_youtube_url(url):
            await interaction.response.send_message(f"加入音樂\n{url}")
            await self.download(url, "append", guild_id)
        else:
            await interaction.response.send_message("Invalid YouTube URL or the video is not available.")

    @app_commands.command(name="remove", description="清除播放清單")
    async def remove(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        
        if guild_id not in self.playlists or not self.playlists[guild_id]:
            await interaction.response.send_message("播放清單為空")
            return
        else:
            self.voice_clients[guild_id].stop()
            self.playlists[guild_id].clear()
            await interaction.response.send_message("清除全部播放清單")          
            
            
    
    @app_commands.command(name="list", description="顯示播放清單")
    async def list(self, interaction: discord.Interaction, page: int):
        guild_id = interaction.guild.id
        if guild_id not in self.playlists:
            self.playlists[guild_id] = deque()

        embed = discord.Embed(title="播放清單", description=f"第 {page} 頁(共{math.ceil(len(self.playlists[guild_id])/10)}頁)", color=0x0000ff)
        show_list = []
        for a in range((page - 1) * 10, page * 10):
            if a < len(self.playlists[guild_id]):
                if a == 0:
                    show_list.append(f"{a + 1}. {self.playlists[guild_id][a]}    (正在播放)")
                else:
                    show_list.append(f"{a + 1}. {self.playlists[guild_id][a]}")
            else:
                break

        for item in show_list:
            embed.add_field(name=item, value="", inline=False)

        await interaction.response.send_message(embed=embed)

    @tasks.loop(seconds=1)
    async def play_next(self):
        try:
            for guild_id, vc in self.voice_clients.items():
                if vc.is_connected() and not vc.is_playing() and self.playlists[guild_id]:
                    file_to_remove = self.playlists[guild_id][0]
                    self.playlists[guild_id].popleft()
                    if file_to_remove not in self.playlists[guild_id]:
                        os.remove(f"downloads/{guild_id}/{file_to_remove}.mp4")
                        print(f"Removed {guild_id}/{file_to_remove}.mp4")
                    if self.playlists[guild_id]:
                        self.play_audio(vc, f"downloads/{guild_id}/{self.playlists[guild_id][0]}.mp4")
        except Exception as e:
            print(f"Error in play_next loop: {e}")

    @app_commands.command(name="vote_skip", description="發起後20秒內音樂頻道有超過1/4使用者同意且同意人數大於反對人數就跳過音樂")
    async def vote_skip(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        self.start_time = time.time()

        self.vote_info[guild_id] = {
            'members': len(interaction.user.voice.channel.members),
            'voted_id': [],
            'vote': 0,
            'agree': 0,
            'disagree': 0
        }
        if interaction.user.voice and self.voice_clients[guild_id].channel and self.voice_clients[guild_id].is_playing():
            view = discord.ui.View()

            agree_button = discord.ui.Button(
                label="同意跳過",
                style=discord.ButtonStyle.blurple
            )
            agree_button.callback = lambda i: self.vote_callback(i, guild_id, "agree")

            disagree_button = discord.ui.Button(
                label="不同意跳過",
                style=discord.ButtonStyle.blurple
            )
            disagree_button.callback = lambda i: self.vote_callback(i, guild_id, "disagree")

            view.add_item(agree_button)
            view.add_item(disagree_button)

            await interaction.response.send_message(view=view)
            self.bot.loop.create_task(self.vote_end(interaction, guild_id))
        else:
            await interaction.response.send_message("You need to be in a voice channel and play music to use this command.")

    async def vote_callback(self, interaction: discord.Interaction, guild_id: int, vote_type: str):
        await interaction.response.send_message(f"等待中！還有{int(20-(time.time()-self.start_time))}秒", ephemeral=True)

        if interaction.user.id not in self.vote_info[guild_id]['voted_id'] and interaction.user in interaction.user.voice.channel.members:
            self.vote_info[guild_id]['voted_id'].append(interaction.user.id)
            self.vote_info[guild_id]['vote'] += 1
            if vote_type == "agree":
                self.vote_info[guild_id]['agree'] += 1
            elif vote_type == "disagree":
                self.vote_info[guild_id]['disagree'] += 1

    async def vote_end(self, interaction: discord.Interaction, guild_id: int):
        await asyncio.sleep(20)
        vote_info = self.vote_info[guild_id]
        await interaction.channel.send(f"{vote_info['vote']}人投票 {vote_info['agree']}人同意跳過 {vote_info['disagree']}人不同意跳過")

        if vote_info['vote'] / vote_info['members'] >= 0.25:
            if vote_info['agree'] > vote_info['disagree']:
                await interaction.channel.send("跳過此首")
                if self.playlists[guild_id]:
                    await interaction.channel.send(f"已跳過音樂{self.playlists[guild_id][0]}")
                    self.voice_clients[guild_id].stop()
                    return

        await interaction.channel.send("繼續收聽")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
