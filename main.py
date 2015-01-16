import os
import re
import time
import html
import random
import string
try:
   import cPickle as pickle
except:
   import pickle

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
                 None if an error occurs or there are no words to build the word cloud
        """
        try:
            tweets = self.twitter_api.harvest_user_timeline(screen_name=twitter_user, max_results=self.MAX_RESULTS)
        except:
            return None
        if tweets == []:
            return None
        words = self.clean_tweets(tweets)
        if words == []:
            return None
        try:
            wordcloud = WordCloud(width=self.WIDTH, height=self.HEIGHT, max_words=self.MAX_WORDS) \
                .generate(' '.join(words))
        except:
            return None
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
            h = h['text']
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

    def save_mentions(self, mentions):
        with open('./mentions', 'wb') as f:
            pickle.dump(mentions, f)

    def load_mentions(self):
        with open('./mentions', 'rb') as f:
            try:
                mentions = pickle.load(f)
            except:
                mentions = []
        return mentions

    def get_new_mentions(self, mentions, last_mention_id=1):
        """ Download the new mentions
        :param mentions: list of mentions already downloaded, the newest mention is at the top
        :param last_mention_id: string containing the id of the last mention. If "mentions" is an empty list then only
                        mentions arrived after this mention are downloaded, otherwise this parameter is ignored
        :return: a list of mentions with the new mentions added at the top
        """
        if mentions:
            last_mention_id = mentions[0]['id_str']
        else:
            last_mention_id = last_mention_id
        new_mentions = self.twitter_api.get_mentions(last_mention_id)
        mentions = new_mentions + mentions
        return mentions

    def handle_mentions(self):
        """ Handle the mentions of this twitter bot.
        :return: number of mentions handled
        """
        mentions_handled = 0
        mentions = self.load_mentions()
        mentions = self.get_new_mentions(mentions, self.settings.read_last_mention_id())
        self.save_mentions(mentions)

        if mentions:
            print("I'm going to handle {0} mention(s).".format(len(mentions)))
        else:
            print("No mentions :(")

        while mentions:
            mention = mentions.pop()
            mentions_handled += 1

            in_reply_to_status_id = mention['id_str']
            self.settings.write_last_mention_id(in_reply_to_status_id)

            if mentions and mentions_handled % 10 == 0:
                old_num_mentions = len(mentions)
                mentions = self.get_new_mentions(mentions, self.settings.read_last_mention_id())
                self.save_mentions(mentions)
                print("\nThere are {0} new mentions, now I have to handle {1} mentions in total.\n".format(len(mentions)-old_num_mentions, len(mentions)))

            print("Handling mention: {0},\nfrom: @{1},\nwith id: {2}".format(mention['text'],
                                                                             mention['user']['screen_name'],
                                                                             mention['id_str']))

            screen_name = mention['user']['screen_name']
            if screen_name == self.BOT_NAME:
                print("Skipping this self mention.\n")
                self.save_mentions(mentions)
                continue

            status = '@' + screen_name + ' '

            if self._contains_hashtag(mention, self.WORDCLOUD_HASHTAGS):
                if len(mention['entities']['user_mentions']) > 1:
                    # in the tweet, besides this bot mention, there's at least another one
                    user_name = self._get_first_mention(mention)
                    if user_name is None:
                        # probably some twitter user tried to build a word cloud of the bot's twitter account
                        print("Error: couldn't extract a user mention, this is weird!\n")
                        self.save_mentions(mentions)
                        continue
                    status += 'here\'s the word cloud for @' + user_name + ' '
                else:
                    user_name = screen_name
                    status += 'here\'s your word cloud'
                    rand_suff = [' :D ', '! ', ' ^^ ', ' :P ', ' .(ಠ⌣ಠ). ', ' ＼(＠O＠)／ ' ,
                                 ' ＼( ｀.∀´)／ ', ' ;) ', ' voilà ', ' ah! ', ' :^) ', ' :o) ', ' :3 ',
                                 ' =] ', ' 8) ', ' B^D ', ' =3 ', ' ;^) ', ' (^o^)丿 ', ' ^ω^ ',
                                 ' ＼(^o^)／ ', ' ＼(◎o◎)／ ', ' （⌒▽⌒） ', ' ( ﾟヮﾟ) ', ' ( ͡° ͜ʖ ͡°) ',
                                 ' (☞ﾟヮﾟ)☞ ']
                    status += random.choice(rand_suff)
                    # uncomment the following line if you get blocked by Twitter because your replies are automated
                    # status += ''.join(random.choice(string.ascii_lowercase) for _ in range(6)) + ' '
                img_file = self.make_wordcloud(user_name)
                if img_file is None:
                    print("Error: failed building the word cloud\n")
                    self.save_mentions(mentions)
                    continue
                title = 'Word cloud of http://twitter.com/' + user_name
                imgur_id = self.upload_image(img_file, title)
                if imgur_id is None:
                    print("Error: failed uploading the word cloud image\n")
                    self.save_mentions(mentions)
                    continue
                imgur_id = imgur_id['id']
                status += 'http://imgur.com/' + imgur_id
            else:
                print("Skipping this mention because there are no relevant hashtags.\n")
                self.save_mentions(mentions)
                continue

            if len(status) <= 140:
                result = self.reply_to(status, in_reply_to_status_id)
                if result is not None:
                    print("Posted this tweet: {0}\n".format(status))
                else:
                    print("Error: tweet post failed\n")
            else:
                print("Error: This status was too long to be posted {0}\n".format(status))
            
            self.save_mentions(mentions)

            # uncomment the following lines if you get rate-limited by twitter
            #sleep_time = 10
            #time.sleep(sleep_time)

        return mentions_handled

    def reply_to(self, status, in_reply_to_status_id, max_errors=3, sleep_seconds=60):
        """
        :param status: text of the tweet
        :param in_reply_to_status_id: id of the tweet to which we should respond.
                                      Note: This parameter will be ignored unless the author of the tweet
                                      this parameter references is mentioned within the status text.
                                      Therefore, you must include @username, where username is the author of the
                                      referenced tweet, within the status.
        :return: see https://dev.twitter.com/rest/reference/post/statuses/update example result,
                 None if an error occurs
        """
        errors = 0
        while True:
            try:
                return self.twitter_api.reply_tweet(status, in_reply_to_status_id)
            except Exception as e:
                errors += 1

                print("Error while trying to post a reply: " + str(e))
                print('Encountered {0} error(s). Retrying in {1} seconds'.format(errors, sleep_seconds))

                if (errors > max_errors):
                    return None

                time.sleep(sleep_seconds)

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

    def run(self, sleep_seconds=60*5):
        """ Run this twitter bot.
        :param sleep_seconds: seconds to wait after having handled some mentions
        :param max_mentions_to_handle: max number of mentions to handle in every batch
        :return:
        """
        while True:
            self.handle_mentions()
            print("I'm going to sleep for {0} seconds\n".format(sleep_seconds))
            time.sleep(sleep_seconds)

    def run_noreply(self):
        """ Run this twitter bot but don't reply to requests, just save mentions so that they can be handled later.
        """
        mentions = self.load_mentions()
        print("Loaded {0} mentions from file\n".format(len(mentions)))
        while True:
            old_num_mentions = len(mentions)
            mentions = self.get_new_mentions(mentions, self.settings.read_last_mention_id())
            self.save_mentions(mentions)
            print("\nThere are {0} new mentions, now there are {1} mentions saved.\n".format(len(mentions)-old_num_mentions, len(mentions)))
            time.sleep(60*5)

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
            except Exception as e:
                errors += 1
                print(e)

                print('Encountered {0} error(s). Retrying in {1} seconds'.format(errors, sleep_seconds))

                if (errors > max_errors):
                    return None

                time.sleep(sleep_seconds)

if __name__ == "__main__":
    s = Settings("./settings.ini")
    stopwords = s.read_stopwords()
    try:
        access_token = s.read_twitter_access_token()
    except:
        access_token = None
    try:
        access_token_secret = s.read_twitter_access_token_secret()
    except:
        access_token_secret = None
    twitter_api = TwitterApi(s.read_twitter_consumer_key(), s.read_twitter_consumer_secret(),
                             access_token, access_token_secret)

    imgur_client = ImgurClient(s.read_imgur_client_id(), s.read_imgur_client_secret(),
                               s.read_imgur_access_token(), s.read_imgur_refresh_token())

    t = TwitterWordCloudBot(twitter_api, imgur_client, stopwords, s)
    t.run()
