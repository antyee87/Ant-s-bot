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

    @app_commands.command(name="play", description="Add the bot into voice channel and play music")
    async def play(self, interaction: discord.Interaction, url: str):
        if self.is_valid_youtube_url(url):
            asyncio.create_task(self.download(url, "appendleft"))
        else:
            await interaction.response.send_message("Invalid YouTube URL or the video is not available.")
        channel = interaction.user.voice.channel

        await interaction.response.send_message(f"Attempting to play audio.\n{url}")
        if isinstance(channel, discord.VoiceChannel):
            if interaction.guild.voice_client:  # 或者使用 guild.voice_channels 也可以
                if interaction.guild.voice_client.channel == channel:
                    self.play_audio(self.vc, f"downloads/{self.playlist[0]}")
            else:
                self.vc = await channel.connect()
                self.play_audio(self.vc, f"downloads/{self.playlist[0]}")
        else:
            await interaction.response.send_message("You need to be in a voice channel to use this command.")

    @app_commands.command(name="disconnect", description="Disconnect the bot from the voice channel")
    async def disconnect(self, interaction: discord.Interaction):
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()
            await interaction.response.send_message("The bot is disconnected.")
        else:
            await interaction.response.send_message("Not connected to a voice channel.")

    @app_commands.command(name="skip", description="Skip the current audio")
    async def skip(self, interaction: discord.Interaction):
        if self.vc and self.vc.is_playing():
            self.vc.stop()
            await interaction.response.send_message("Current music is skipped.")
        else:
            await interaction.response.send_message("No music is currently playing.")

    @app_commands.command(name="add", description="Add music into the play list")
    async def add(self, interaction: discord.Interaction, url: str):
        if self.is_valid_youtube_url(url):
            asyncio.create_task(self.download(url, "append"))
            await interaction.response.send_message(f"The song is added into the playlist.\n{url}")
        else:
            await interaction.response.send_message("Invalid YouTube URL or the video is not available.")
    
    @app_commands.command(name="list", description="Show the music playlist")
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

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
