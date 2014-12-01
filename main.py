import os
import re
import time
import html

from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError, ImgurClientRateLimitError
from twitter import TwitterHTTPError
from wordcloud import WordCloud

from settings import Settings
from twitterapi import TwitterApi


class TwitterWordCloudBot:
    def __init__(self, twitter_api, imgur_client, stopwords, settings):
        self.twitter_api = twitter_api
        self.imgur_client = imgur_client
        self.stopwords = stopwords
        self.settings = settings

        # twitter name of the bot account
        self.BOT_NAME = settings.read_bot_name()

        # hashtags to which this bot respond
        self.WORDCLOUD_HASHTAGS = settings.read_wordcloud_hashtags()

        # max number of words displayed in the image
        self.MAX_WORDS = settings.read_max_words()

        # directory where images are saved
        self.OUTPUT_DIR = settings.read_output_dir()

        # max number of tweets (including retweets) downloaded
        self.MAX_RESULTS = settings.read_max_results()

        # width and height of the generated image
        self.WIDTH = settings.read_width()
        self.HEIGHT = settings.read_height()

    def make_wordcloud(self, twitter_user):
        """ Build the word cloud png image of a twitter user
        :param twitter_user: name of the twitter account (string)
        :return: path to the word cloud image (string),
                 None if an error occurs
        """
        try:
            tweets = self.twitter_api.harvest_user_timeline(screen_name=twitter_user, max_results=self.MAX_RESULTS)
        except:
            return None
        if tweets == []:
            return None
        words = self.clean_tweets(tweets)
        wordcloud = WordCloud(width=self.WIDTH, height=self.HEIGHT, max_words=self.MAX_WORDS) \
            .generate(' '.join(words))
        ts = str(int(time.time()))
        img_file = os.path.join(self.OUTPUT_DIR, ts + twitter_user + ".png")
        wordcloud.to_file(img_file)
        return img_file

    @staticmethod
    def _contains_hashtag(mention, hashtags, lowercase=True):
        """
        :param mention: mention object
        :param hashtags: list of hashtags without the #, e.g.'wordcloud' not '#wordcloud' (list of string)
        :param lowercase: True if hashtags in the mention should be converted to lowercase before comparison
        :return: True if the mention contains the hashtag, False otherwise
        """
        for h in mention['entities']['hashtags']:
            if lowercase:
                h = h.lower()
            if h in hashtags:
                return True
        return False

    def _get_first_mention(self, mention):
        """
        :param mention: mention object
        :return: the screen name (string) of the first user mentioned in the tweet that is not this bot,
                 if there's none return None
        """
        for u in mention['entities']['user_mentions']:
            if u['screen_name'] != self.BOT_NAME:
                return u['screen_name']
        return None

    def handle_mentions(self, max_mentions_to_handle=5):
        """ Handle the mentions of this twitter bot.
        :param max_mentions_to_handle: max number of mentions to handle, the rest will be handled the next time
                                       this function is called
        :return:
        """
        mentions_handled = 0
        mentions = self.twitter_api.get_mentions(self.settings.read_last_mention_id())

        if len(mentions) > 0:
            print("I'm going to handle {0} mention(s).".format(len(mentions)))
        else:
            print("No mentions :(")

        for mention in reversed(mentions):
            if mentions_handled >= max_mentions_to_handle:
                print("Handled {0} mention(s), enough!".format(max_mentions_to_handle))
                break

            print("Handling mention: {0},\nfrom: @{1},\nwith id: {2}".format(mention['text'],
                                                                             mention['user']['screen_name'],
                                                                             mention['id_str']))
            in_reply_to_status_id = mention['id_str']
            self.settings.write_last_mention_id(in_reply_to_status_id)

            screen_name = mention['user']['screen_name']
            if screen_name == self.BOT_NAME:
                print("Skipping this self mention.\n")
                mentions_handled += 1
                continue

            status = '@' + screen_name + ' '

            if self._contains_hashtag(mention, self.WORDCLOUD_HASHTAGS):
                if len(mention['entities']['user_mentions']) > 1:
                    # in the tweet, besides this bot mention, there's at least another one
                    user_name = self._get_first_mention(mention)
                    if user_name is None:
                        print("Error: couldn't extract a user mention, this is weird!\n")
                        mentions_handled += 1
                        continue
                    status += 'here\'s the word cloud for @' + user_name + ' '
                else:
                    user_name = screen_name
                    status += 'here\'s your word cloud '
                img_file = self.make_wordcloud(user_name)
                if img_file is None:
                    print("Error: failed building the word cloud\n")
                    mentions_handled += 1
                    continue
                title = 'Word cloud of http://twitter.com/' + user_name
                try:
                    imgur_id = self.upload_image(img_file, title)['id']
                except KeyError:
                    print("Error: image upload failed\n")
                    mentions_handled += 1
                    continue
                status += 'http://imgur.com/' + imgur_id
            else:
                print("Skipping this mention because there are no relevant hashtags.\n")
                mentions_handled += 1
                continue

            if len(status) <= 140:
                try:
                    result = self.reply_to(status, in_reply_to_status_id)
                    if result is not None:
                        print("Posted this tweet: {0}\n".format(status))
                    else:
                        print("Error: tweet post failed\n")
                except TwitterHTTPError as e:
                    print("Error: " + str(e) + "\n")
                except:
                    print("Error: tweet post failed\n")
            else:
                print("Error: This status was too long to be posted {0}\n".format(status))

            mentions_handled += 1
            time.sleep(30)

    def reply_to(self, status, in_reply_to_status_id):
        """
        :param status: text of the tweet
        :param in_reply_to_status_id: id of the tweet to which we should respond.
                                      Note: This parameter will be ignored unless the author of the tweet
                                      this parameter references is mentioned within the status text.
                                      Therefore, you must include @username, where username is the author of the
                                      referenced tweet, within the status.
        :return: see https://dev.twitter.com/rest/reference/post/statuses/update example result
        """
        return self.twitter_api.reply_tweet(status, in_reply_to_status_id)

    def clean_tweets(self, tweets, min_length=2):
        """ Given an array of tweets, remove the retweets (tweets that start with "RT @"), remove non-alphanumeric
            characters and remove the stopwords.
        :param tweets: array of tweets objects
        :param min_length: min length of a word
        :return: array of words
        """
        words = []
        langs = {} # for every language, keep track of how many times it is used
        for t in tweets:
            text = t['text']
            if text.find('RT @') == 0:
                # ignore retweets
                continue
            text = self.clean_text(text)

            if 'lang' in t:
                if t['lang'] in self.stopwords:
                    stopwords = self.stopwords[t['lang']]
                    try:
                        langs[t['lang']] += 1
                    except KeyError:
                        langs[t['lang']] = 1
                else:
                    # if t['lang'] is not in self.stopwords, we don't have a stopword dictionary for this language.
                    stopwords = None
            elif len(langs) > 1:
                # if 'lang' is not in t, twitter couldn't recognise the language of this tweet
                # so use the most used language for this stream of tweets (maybe we are lucky)
                max_cnt = 0
                for l, cnt in langs.items():
                    if cnt > max_cnt:
                        max_cnt = cnt
                        max_l = l
                stopwords = self.stopwords[max_l]
            else:
                stopwords = None

            for word in text.split():
                if len(word) >= min_length and (stopwords is None or word not in stopwords):
                    words.append(word)
        return words

    P_emails = re.compile(r'\w+@\w+\.\w+')
    P_retweets = re.compile(r'(RT )?@[\w]+')
    P_links = re.compile(r'https?://.+?(\s|$)')
    P_symbols = re.compile(r'[^\w\s]')
    P_multispaces = re.compile(r'\s+')
    def clean_text(self, text):
        """ Unescape html entities, transform to lowercase, remove emails (e.g. user@domain.com),
            tweet mentions (e.g. @user), urls, non-alphanumeric symbols and collpase all multi-spaces into one.
        :param text: text to clean
        :return: text cleaned
        """
        text = html.unescape(text).lower()
        text = re.sub(self.P_emails, " ", text)
        text = re.sub(self.P_retweets, " ", text)
        text = re.sub(self.P_links, " ", text)
        text = re.sub(self.P_symbols, " ", text)
        text = re.sub(self.P_multispaces, " ", text)
        text = text.strip()
        return text

    def run(self, sleep_seconds=60*5, max_mentions_to_handle=5):
        """ Run this twitter bot.
        :param sleep_seconds: seconds to wait after having handled some mentions
        :param max_mentions_to_handle: max number of mentions to handle in every batch
        :return:
        """
        while True:
            self.handle_mentions(max_mentions_to_handle)
            print("I'm going to sleep for {0} seconds\n".format(sleep_seconds))
            time.sleep(sleep_seconds)

    def upload_image(self, image_path, title, max_errors=3, sleep_seconds=60):
        """ Try to upload the image to imgur.com.
        :param image_path: path to the image file
        :param title: title of the image
        :param max_errors: max number of retries
        :param sleep_seconds: number of seconds to wait when an error happens
        :return: an imgur object (use `id` key to get the id to use in https://imgur.com/<id>),
                 None if an error occurs
        """
        config = {'title': title,
                  'name': title,
                  'description': title + '\n' + self.settings.read_description_image_str()}
        errors = 0
        while True:
            try:
                print("I'm going to upload this image: {0}".format(image_path))
                return self.imgur_client.upload_from_path(image_path, config=config, anon=False)
            except ImgurClientError as e:
                errors += 1
                print(e.error_message)
                print(e.status_code)

                print('Encountered {0} error(s). Retrying in {1} seconds'.format(errors, sleep_seconds))

                if (errors > max_errors):
                    return None

                time.sleep(sleep_seconds)
            except ImgurClientRateLimitError:
                return None
            except:
                return None

if __name__ == "__main__":
    s = Settings("./settings.ini")
    stopwords = s.read_stopwords()

    twitter_api = TwitterApi(s.read_twitter_consumer_key(), s.read_twitter_consumer_secret(),
                             s.read_twitter_access_token(), s.read_twitter_access_token_secret())

    imgur_client = ImgurClient(s.read_imgur_client_id(), s.read_imgur_client_secret(),
                               s.read_imgur_access_token(), s.read_imgur_refresh_token())

    t = TwitterWordCloudBot(twitter_api, imgur_client, stopwords, s)
    t.run()