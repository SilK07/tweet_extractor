import streamlit as st
import tweepy
import json
import os
import zipfile
from datetime import datetime, timedelta
import time

# Replace the following strings with your own credentials
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAGMwuAEAAAAAycDcTGaLRRkXuYQUyUQGxdhpuHE%3DvgsT4QFA0sZi2UGkcVHsDi8tsd40gFryqQUymkJbtvofBoonJ5"

# Authenticate to Twitter using the Bearer Token
client = tweepy.Client(bearer_token=BEARER_TOKEN)

# Global flag to control the extraction process
stop_extraction = False

def get_tweets_in_date_range(username, start_date, end_date, next_token=None):
    start_date = start_date.replace(microsecond=0).isoformat("T") + "Z"
    end_date = end_date.replace(microsecond=0).isoformat("T") + "Z"
    user = client.get_user(username=username)
    user_id = user.data.id
    all_tweets = []
    media_dict = {}

    while True:
        try:
            tweets = client.get_users_tweets(
                id=user_id,
                start_time=start_date,
                end_time=end_date,
                tweet_fields=["created_at", "text", "attachments"],
                expansions=["attachments.media_keys"],
                media_fields=["url", "preview_image_url", "type", "variants"],
                max_results=100,
                pagination_token=next_token
            )

            if tweets.data:
                all_tweets.extend(tweets.data)
                if tweets.includes and 'media' in tweets.includes:
                    media_dict.update({media.media_key: media for media in tweets.includes['media']})

                if 'next_token' in tweets.meta:
                    next_token = tweets.meta['next_token']
                else:
                    break
            else:
                break

        except tweepy.TooManyRequests as e:
            retry_time = datetime.now() + timedelta(minutes=15)
            st.warning(f"Rate limit reached. Next attempt scheduled at {retry_time.strftime('%Y-%m-%d %H:%M:%S')}.")
            time.sleep(15 * 60)
            continue

        except tweepy.TweepyException as e:
            st.error(f"Error occurred: {e}")
            break

    return all_tweets, media_dict

def store_tweets_in_file(tweets, media_dict, batch_number, start_date, end_date):
    filename = f"tweets_batch_{batch_number}_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.txt"
    with open(filename, "w", encoding="utf-8") as file:
        for tweet in tweets:
            file.write(f"{tweet.created_at} - {tweet.text}\n")
            if 'attachments' in tweet and 'media_keys' in tweet.attachments:
                for media_key in tweet.attachments['media_keys']:
                    media = media_dict.get(media_key)
                    if media:
                        if media.type == 'photo':
                            file.write(f"Photo URL: {media.url}\n")
                        elif media.type == 'video':
                            for variant in media.variants:
                                if variant.get('content_type') == 'video/mp4':
                                    file.write(f"Video URL: {variant.get('url')}\n")
                                    break
                        elif media.type == 'animated_gif':
                            for variant in media.variants:
                                if variant.get('content_type') == 'video/mp4':
                                    file.write(f"GIF URL: {variant.get('url')}\n")
                                    break
            file.write("\n")
    return filename

def main():
    global stop_extraction

    st.title("Twitter Data Extractor")

    username = st.text_input("Enter Twitter Username")
    start_date = st.date_input("Start Date", min_value=datetime(2006, 3, 21).date())
    stop_date = st.date_input("Stop Date", min_value=start_date)

    extract_button = st.button("Extract Tweets")
    stop_button = st.button("Stop Extraction")

    if extract_button:
        stop_extraction = False
        start_date = datetime.combine(start_date, datetime.min.time())
        stop_date = datetime.combine(stop_date, datetime.min.time())
        end_date = start_date + timedelta(days=10)
        batch_number = 1
        next_token = None
        zip_filename = f"{username}_tweets.zip"

        with zipfile.ZipFile(zip_filename, "w") as zipf:
            while start_date <= stop_date:
                if stop_extraction:
                    st.write("Extraction stopped by user.")
                    break

                st.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching tweets from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
                tweets, media_dict = get_tweets_in_date_range(username, start_date, end_date, next_token=next_token)

                if tweets:
                    filename = store_tweets_in_file(tweets, media_dict, batch_number, start_date, end_date)
                    zipf.write(filename)
                    os.remove(filename)
                    st.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetched {len(tweets)} tweets for batch {batch_number}.")
                else:
                    st.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No tweets found in this range.")

                start_date = end_date
                end_date += timedelta(days=10)
                batch_number += 1

        if os.path.exists(zip_filename):
            with open(zip_filename, "rb") as f:
                st.download_button("Download All Data", f, file_name=zip_filename)

    if stop_button:
        stop_extraction = True

if __name__ == "__main__":
    main()
