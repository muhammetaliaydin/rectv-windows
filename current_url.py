import json
import aiohttp
import logging
import os
import asyncio
from typing import Optional
import sys
import requests

class CurrentURL:
    def __init__(self):
        self.config_path = "config.json"
        self.config = self._load_config()
        self.session = None

    def _load_config(self) -> dict:
        """config.json dosyasını yükle"""
        try:
            is_exe = getattr(sys, 'frozen', False)
            
            if is_exe:
                config_path = os.path.join(os.path.dirname(sys.executable), self.config_path)
            else:
                config_path = os.path.join(os.path.dirname(__file__), self.config_path)
            
            # Config dosyası yoksa internetten indir
            if not os.path.exists(config_path):
                print("Config dosyası bulunamadı, internetten indiriliyor...")
                try:
                    response = requests.get("https://raw.githubusercontent.com/muhammetaliaydin/rectv-windows/refs/heads/master/config.json")
                    if response.status_code == 200:
                        with open(config_path, 'w', encoding='utf-8') as f:
                            json.dump(response.json(), f, indent=4, ensure_ascii=False)
                        print("Config dosyası indirildi!")
                    else:
                        print("Config dosyası indirilemedi!")
                        return {}
                except Exception as e:
                    print("Config dosyası indirme hatası!")
                    return {}
            
            # Config dosyasını oku
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                if not config.get("main_urls"):
                    print("Config dosyasında 'main_urls' bulunamadı!")
                    return {}
                    
                return config
        except FileNotFoundError:
            print(f"Config dosyası bulunamadı: {self.config_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Config dosyası JSON formatında değil!")
            return {}
        except Exception as e:
            print(f"Config dosyası yüklenirken hata oluştu!")
            return {}

    def _save_config(self, config: dict):
        """config.json dosyasını kaydet"""
        try:
            is_exe = getattr(sys, 'frozen', False)
            
            if is_exe:
                config_path = os.path.join(os.path.dirname(sys.executable), self.config_path)
            else:
                config_path = os.path.join(os.path.dirname(__file__), self.config_path)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Config dosyası kaydedilemedi!")

    async def initialize(self):
        """Session'ı başlat"""
        self.session = aiohttp.ClientSession()
        return self

    async def close(self):
        """Session'ı kapat"""
        if self.session:
            await self.session.close()

    async def test_url(self, url: str) -> bool:
        """Belirtilen URL'nin çalışıp çalışmadığını test et"""
        try:
            test_url = f"{url}/api/channel/by/filtres/0/0/0/{self.config['sw_key']}/"
            
            async with self.session.get(
                test_url, 
                headers={"user-agent": "okhttp/4.12.0"},
                timeout=5
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    try:
                        json.loads(text)
                        return True
                    except json.JSONDecodeError:
                        return False
                return False
        except Exception:
            return False

    async def update_config(self) -> bool:
        """Update URL'den yeni config dosyasını indir"""
        if not self.config.get("update_url"):
            return False

        try:
            async with self.session.get(self.config["update_url"]) as response:
                if response.status == 200:
                    new_config = await response.json()
                    self._save_config(new_config)
                    self.config = new_config
                    return True
                return False
        except Exception as e:
            print(f"Config güncelleme hatası: {e}")
            return False

    async def get_working_url(self) -> Optional[tuple[str, str]]:
        """Çalışan bir URL ve sw_key değerini tuple olarak döndür"""
        sw_key = self.config.get("sw_key")
        if not sw_key:
            print("Config dosyasında 'sw_key' bulunamadı!")
            return None

        for url in self.config.get("main_urls", []):
            if await self.test_url(url):
                return (url, sw_key)

        if await self.update_config():
            sw_key = self.config.get("sw_key")
            for url in self.config.get("main_urls", []):
                if await self.test_url(url):
                    return (url, sw_key)

        print("Hiçbir URL çalışmıyor!")
        return None

async def get_api_url() -> Optional[tuple[str, str]]:
    """Çalışan API URL'sini ve sw_key değerini tuple olarak döndür"""
    current_url = await CurrentURL().initialize()
    try:
        working_url = await current_url.get_working_url()
        if working_url:
            url, sw_key = working_url  # tuple olarak dönen değerleri ayır
            return (url, sw_key)  # URL ve sw_key'i tuple olarak döndür
        else:
            print("Çalışan API URL'si bulunamadı!")
            return None
    finally:
        await current_url.close()

async def test_all_urls():
    """Tüm URL'leri test et ve durumlarını raporla"""
    current_url = await CurrentURL().initialize()
    try:
        print("\nURL Test Raporu:")
        print("-" * 50)
        
        # Config kontrolü
        if not current_url.config:
            print("Config dosyası yüklenemedi!")
            return
            
        # main_urls listesi kontrolü
        main_urls = current_url.config.get("main_urls", [])
        if not main_urls:
            print("Config dosyasında main_urls listesi boş veya bulunamadı!")
            print(f"Mevcut config içeriği: {current_url.config}")
            return
        
        # URL'leri test et ve ilk çalışanı bul
        print("Config'deki URL'ler test ediliyor:")
        for url in main_urls:
            is_working = await current_url.test_url(url)
            status = "✓ Çalışıyor" if is_working else "✗ Çalışmıyor"
            print(f"{url}: {status}")
            
            if is_working:
                print(f"\nÇalışan URL bulundu: {url}")
                print("Diğer URL'ler test edilmeyecek.")
                return
        
        print("\nHiçbir URL çalışmıyor!")
        print("Config güncellemesi deneniyor...")
        
        # Config güncelleme sonrası tekrar dene
        if await current_url.update_config():
            for url in current_url.config.get("main_urls", []):
                is_working = await current_url.test_url(url)
                status = "✓ Çalışıyor" if is_working else "✗ Çalışmıyor"
                print(f"{url}: {status}")
                
                if is_working:
                    print(f"\nGüncelleme sonrası çalışan URL bulundu: {url}")
                    return
            
            print("\nGüncelleme sonrası da hiçbir URL çalışmıyor!")
        else:
            print("Config güncellenemedi!")
            
    finally:
        await current_url.close()

if __name__ == "__main__":
    # Debug log ayarlarını kaldır
    logging.basicConfig(
        level=logging.ERROR,
        format='%(message)s'
    )
    
    # Tüm URL'leri test et
    asyncio.run(test_all_urls()) 