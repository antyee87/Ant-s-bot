import discord
from discord.ext import tasks, commands
from discord import app_commands
from discord import FFmpegPCMAudio, PCMVolumeTransformer
import subprocess
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
import logging

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients = {}  # 存储每个服务器的语音客户端
        self.playlists = {}  # 存储每个服务器的播放列表
        self.vote_info = {}  # 存储每个服务器的投票信息
        self.playing={}
        self.remove_file.start()
        self.video_regex = re.compile(
            r'(https?://)?(www\.)?((youtube\.com/watch\?v=)|(youtu\.be/)|(music\.youtube\.com/watch\?v=)).+'
        )
        self.playlist_regex = re.compile(
            r'(https?://)?(www\.)?((youtube\.com)|(youtu\.?be)|(music\.youtube\.com))/playlist\?list=.+'
        )
        
        for filename in os.listdir("downloads"):
            file_path = os.path.join("downloads", filename)
            shutil.rmtree(file_path)  # 删除文件夹及其所有内容

    async def add_playlists(self, url, mode, guild_id,index=None):  
        def process_playlist():
            pl = Playlist(url)
            a=0
            for video in pl.videos:  
                if mode == "appendleft" :
                    self.playlists[guild_id]['title'].insert(a,video.title)
                    self.playlists[guild_id]['url'].insert(a,video.watch_url)
                    if a==0:
                        if guild_id in self.playing and self.voice_clients[guild_id].is_playing() and self.playlists[guild_id]["title"][0]!=self.playing[guild_id]["title"]:
                            self.voice_clients[guild_id].stop()
                elif mode=="append":
                    self.playlists[guild_id]['title'].append(video.title)
                    self.playlists[guild_id]['url'].append(video.watch_url)
                elif mode=="insert":
                    self.playlists[guild_id]['title'].insert(index+a,video.title)
                    self.playlists[guild_id]['url'].insert(index+a,video.watch_url)
                a+=1  
        if guild_id not in self.playlists:
                self.playlists[guild_id]={
                        "title":deque(),
                        "url":deque()
                    }     
        if self.playlist_regex.match(url): 
            await asyncio.to_thread(process_playlist)
        
        elif self.video_regex.match(url):
            video = YouTube(url)
            if mode == "appendleft":
                self.playlists[guild_id]['title'].appendleft(video.title)
                self.playlists[guild_id]['url'].appendleft(url)  
                if guild_id in self.playing and self.voice_clients[guild_id].is_playing() and self.playlists[guild_id]["title"][0]!=self.playing[guild_id]["title"]:
                        self.voice_clients[guild_id].stop()
            elif mode=="append":
                self.playlists[guild_id]['title'].append(video.title)
                self.playlists[guild_id]['url'].append(url)
            elif mode=="insert":
                self.playlists[guild_id]['title'].insert(index,video.title)
                self.playlists[guild_id]['url'].insert(index,url)
            
    def get_mean_volume(self,file_path):
        result = subprocess.run(
        ["ffmpeg", "-i", file_path, "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "/dev/null"],
        stderr=subprocess.PIPE,
        text=True
        )
        output = result.stderr

        # Regex to find the mean volume from the output
        mean_match = re.search(r"mean_volume: ([\-\d\.]+) dB", output)
        
        if mean_match:
            mean_volume = float(mean_match.group(1))
            return mean_volume
        else:
            raise ValueError("Could not find volume levels in ffmpeg output")
 
            
    def play_audio(self,guild_id):     
        if not os.path.exists(f"downloads/{guild_id}"):
            os.makedirs(f"downloads/{guild_id}") 
        yt = YouTube(self.playlists[guild_id]["url"][0], on_progress_callback=on_progress)
        ys = yt.streams.get_audio_only()
        filepath = ys.download(f"downloads/{guild_id}")
        if guild_id not in self.playing:
                self.playing[guild_id]={
                    "title":"",
                    "filename":""
                }
        self.playing[guild_id]["title"]=self.playlists[guild_id]["title"][0]
        self.playing[guild_id]["filename"]=os.path.basename(filepath)
        mean_volume=self.get_mean_volume(filepath)
        relative_volume=round(math.pow(10,(-16-mean_volume)/20),2)
        source = FFmpegPCMAudio(source=filepath)
        audio_source = PCMVolumeTransformer(source,volume=relative_volume)
        self.voice_clients[guild_id].play(audio_source, after = lambda e:self.after_playing(guild_id))
        
        
    def is_valid_youtube_url(self, url: str) -> bool:
        try:
            if self.video_regex.match(url) or self.playlist_regex.match(url):
                return True
            else:
                return False
        except (VideoUnavailable, RegexMatchError):
            return False

    @app_commands.command(name="play", description="將機器人加入頻道並插入播放音樂(插入單曲或播放清單)")
    @app_commands.describe(url="可以加入歌曲或播放清單")
    async def play(self, interaction: discord.Interaction, url: Optional[str] = None):
        guild_id = interaction.guild.id
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            if url != None:
                if self.is_valid_youtube_url(url):
                    await interaction.response.send_message(f"播放音樂\n{url}")
                    asyncio.create_task(self.add_playlists(url, "appendleft", guild_id))
                else:
                    await interaction.response.send_message("無效輸入")
                    return
            else:
                if self.voice_clients[guild_id].is_playing():
                    await interaction.response.send_message(f"已播放音樂\n{self.playlists[guild_id]["title"][0]}")
                    return
                else:
                    await interaction.response.send_message(f"播放音樂\n{self.playlists[guild_id]["title"][0]}")

            if interaction.guild.voice_client:
                if interaction.guild.voice_client.channel != channel:
                    await interaction.guild.voice_client.move_to(channel)
            else:
                self.voice_clients[guild_id] = await channel.connect()

            self.play_audio(guild_id)
        else:
            await interaction.response.send_message("你尚未連接到任何語音頻道")

    @app_commands.command(name="leave", description="離開語音頻道(會保留播放清單)")
    async def leave(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            await self.voice_clients[guild_id].disconnect()
            await interaction.response.send_message("機器人已離開語音頻道QwQ")
        else:
            await interaction.response.send_message("機器人尚未連接到任何語音頻道")

    @app_commands.command(name="skip", description="跳過當前音樂")
    async def skip(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_playing():
            await interaction.response.send_message(f"已跳過音樂\n{self.playlists[guild_id]["title"][0]}")
            self.voice_clients[guild_id].stop()
        else:
            await interaction.response.send_message("目前沒有音樂正在播放")

    @app_commands.command(name="add", description="將youtube音樂(播放清單)加入播放清單")
    @app_commands.describe(url="可以加入歌曲或播放清單",index="從第幾首歌後開始加")
    async def add(self, interaction: discord.Interaction, url: str,index:Optional[int]=None):
        guild_id = interaction.guild.id
        if index == None:
            if self.is_valid_youtube_url(url):
                await interaction.response.send_message(f"加入音樂\n{url}")
                await self.add_playlists(url, "append", guild_id)
            else:
                await interaction.response.send_message("無效輸入")
        else:
            if index >=1 and index <= len(self.playlists[guild_id]["title"]):
                if self.is_valid_youtube_url(url):
                    await interaction.response.send_message(f"加入音樂\n{url}")
                    await self.add_playlists(url,"insert", guild_id,index)
                else:
                    await interaction.response.send_message("無效輸入")
            else:
                await interaction.response.send_message("無效輸入")
                
            
    @app_commands.command(name="remove", description="清除播放清單")
    async def remove(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        
        if guild_id not in self.playlists or not self.playlists[guild_id]["title"]:
            await interaction.response.send_message("播放清單為空")
            return
        else:  
            self.playlists[guild_id]["title"].clear()
            self.playlists[guild_id]["url"].clear()
            self.voice_clients[guild_id].stop()
            await interaction.response.send_message("清除全部播放清單")          
            
            
    
    @app_commands.command(name="list", description="顯示播放清單")
    async def list(self, interaction: discord.Interaction, page:Optional[int]=1):
        guild_id = interaction.guild.id
        if guild_id not in self.playlists:
            self.playlists[guild_id]={
                    "title":deque(),
                    "url":deque()
                }
        embed = discord.Embed(title="播放清單", description=f"第 {page} 頁(共{math.ceil(len(self.playlists[guild_id]["title"])/10)}頁)", color=0x0000ff)
        for a in range((page - 1) * 10, page * 10):
            if a < len(self.playlists[guild_id]["title"]):
                if a == 0 and self.voice_clients[guild_id].is_playing():
                    embed.add_field(name="",value=f"{a + 1}. [{self.playlists[guild_id]["title"][a]}]({self.playlists[guild_id]["url"][a]})    (正在播放)",inline=False)
                else:
                    embed.add_field(name="",value=f"{a + 1}. [{self.playlists[guild_id]["title"][a]}]({self.playlists[guild_id]["url"][a]})", inline=False)
            else:
                break
    
        await interaction.response.send_message(embed=embed)
        
    
    def after_playing(self,guild_id):
        async def disconnect():
            await self.voice_clients[guild_id].disconnect()
        if self.voice_clients[guild_id].is_connected() and self.playlists[guild_id]["title"][0]==self.playing[guild_id]["title"]:  
            self.playlists[guild_id]["title"].popleft()
            self.playlists[guild_id]["url"].popleft()
        
        if self.playlists[guild_id]["title"]:
            self.play_audio(guild_id)
        else:
            asyncio.run_coroutine_threadsafe(disconnect(), self.bot.loop)
            
                
    @tasks.loop(minutes=3)
    async def remove_file(self):
        for guild_id in self.playlists:
            for filename in os.listdir(f"downloads/{guild_id}"):
                if not filename in self.playing[guild_id]["filename"]:
                    try:
                        file_path = os.path.join(f"downloads/{guild_id}", filename)
                        os.remove(file_path)
                    except Exception as e:
                        logging.basicConfig(level=logging.ERROR)
                        logger = logging.getLogger(__name__)
                        logger.error(e)
        
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
            await interaction.response.send_message("你尚未連接到任何音樂頻道")

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
                    await interaction.channel.send(f"已跳過音樂{self.playlists[guild_id]["title"][0]}")
                    self.voice_clients[guild_id].stop()
                    return

        await interaction.channel.send("繼續收聽")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
