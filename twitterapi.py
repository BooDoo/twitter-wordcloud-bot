from http.client import BadStatusLine
import time
from urllib.error import URLError
import twitter
import os


class TwitterApi():
    def __init__(self, consumer_key, consumer_secret, access_token=None, access_token_secret=None):
        self.twitter_api = self.oauth_login(consumer_key, consumer_secret, access_token, access_token_secret)

    @staticmethod
    def oauth_login(consumer_key, consumer_secret, access_token, access_token_secret):
        if not access_token or not access_token_secret:
            oauth_file = './twitter_oauth'
            if not os.path.exists(oauth_file):
                twitter.oauth_dance("App", consumer_key, consumer_secret, oauth_file)
            access_token, access_token_secret = twitter.read_token_file(oauth_file)

        auth = twitter.oauth.OAuth(access_token, access_token_secret,
                                   consumer_key, consumer_secret)

        return twitter.Twitter(auth=auth)

    def make_twitter_request(self, twitter_api_func, max_errors=10, *args, **kw):
        # A nested helper function that handles common HTTPErrors. Return an updated
        # value for wait_period if the problem is a 500 level error. Block until the
        # rate limit is reset if it's a rate limiting issue (429 error). Returns None
        # for 401 and 404 errors, which requires special handling by the caller.
        def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):
            if wait_period > 3600: # Seconds
                print('Too many retries. Quitting.')
                raise e

            # See https://dev.twitter.com/docs/error-codes-responses for common codes

            if e.e.code == 401:
                print('Encountered 401 Error (Not Authorized)')
                return None
            elif e.e.code == 404:
                print('Encountered 404 Error (Not Found)')
                return None
            elif e.e.code == 429:
                print('Encountered 429 Error (Rate Limit Exceeded)')
                if sleep_when_rate_limited:
                    print("Retrying in 15 minutes...ZzZ...")
                    time.sleep(60*15 + 5)
                    print('...ZzZ...Awake now and trying again.')
                    return 2
                else:
                    raise e # Caller must handle the rate limiting issue
            elif e.e.code in (500, 502, 503, 504):
                print('Encountered {0} Error. Retrying in {1} seconds' \
                    .format(e.e.code, wait_period))
                time.sleep(wait_period)
                wait_period *= 1.5
                return wait_period
            else:
                raise e

        # End of nested helper function

        wait_period = 2
        error_count = 0

        while True:
            try:
                return twitter_api_func(*args, **kw)
            except twitter.api.TwitterHTTPError as e:
                error_count = 0
                wait_period = handle_twitter_http_error(e, wait_period)
                if wait_period is None:
                    return
            except URLError as e:
                error_count += 1
                print("URLError encountered. Continuing.")
                if error_count > max_errors:
                    print("Too many consecutive errors...bailing out.")
                    raise
            except BadStatusLine as e:
                error_count += 1
                print("BadStatusLine encountered. Continuing.")
                if error_count > max_errors:
                    print("Too many consecutive errors...bailing out.")
                    raise

    def harvest_user_timeline(self, screen_name=None, user_id=None, max_results=3200):
        assert (screen_name != None) != (user_id != None), \
        "Must have screen_name or user_id, but not both"

        kw = {  # Keyword args for the Twitter API call
            'count': 200,
            'trim_user': 'true',
            'include_rts' : 'true',
            'since_id' : 1
            }

        if screen_name:
            kw['screen_name'] = screen_name
        else:
            kw['user_id'] = user_id

        max_pages = 16
        results = []

        tweets = self.make_twitter_request(self.twitter_api.statuses.user_timeline, **kw)

        if tweets is None: # 401 (Not Authorized) - Need to bail out on loop entry
            tweets = []

        results += tweets

        print('Fetched {0} tweets'.format(len(tweets)))

        page_num = 1

        # Many Twitter accounts have fewer than 200 tweets so you don't want to enter
        # the loop and waste a precious request if max_results = 200.

        # Note: Analogous optimizations could be applied inside the loop to try and
        # save requests. e.g. Don't make a third request if you have 287 tweets out of
        # a possible 400 tweets after your second request. Twitter does do some
        # post-filtering on censored and deleted tweets out of batches of 'count', though,
        # so you can't strictly check for the number of results being 200. You might get
        # back 198, for example, and still have many more tweets to go. If you have the
        # total number of tweets for an account (by GET /users/lookup/), then you could
        # simply use this value as a guide.

        if max_results == kw['count']:
            page_num = max_pages # Prevent loop entry

        while page_num < max_pages and len(tweets) > 0 and len(results) < max_results:

            # Necessary for traversing the timeline in Twitter's v1.1 API:
            # get the next query's max-id parameter to pass in.
            # See https://dev.twitter.com/docs/working-with-timelines.
            kw['max_id'] = min([ tweet['id'] for tweet in tweets]) - 1

            tweets = self.make_twitter_request(self.twitter_api.statuses.user_timeline, **kw)
            results += tweets

            print('Fetched {0} tweets'.format(len(tweets)))

            page_num += 1

        print('Done fetching tweets')

        return results[:max_results]

    def get_mentions(self, last_mention_id=1):
        kw = {  # Keyword args for the Twitter API call
            'count': 200,
            'trim_user': 'false',
            'include_rts': 'true',
            'since_id' : last_mention_id
            }

        mentions = self.make_twitter_request(self.twitter_api.statuses.mentions_timeline, **kw)
        if mentions is None:
            mentions = []
        return mentions

    def reply_tweet(self, status, in_reply_to_status_id):
        kw = {  # Keyword args for the Twitter API call
            'status': status,
            'in_reply_to_status_id': in_reply_to_status_id,
            }
        return self.make_twitter_request(self.twitter_api.statuses.update, **kw)