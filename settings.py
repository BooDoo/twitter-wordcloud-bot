import configparser

class Settings(object):
    def __init__(self, settings_file):
        self.settings_file = settings_file
        self.config = configparser.ConfigParser()
        self.config.read(self.settings_file)

        self.IMGUR = 'imgur'
        self.TWITTER = 'twitter'
        self.CONFIGS = 'configs'

    def read_twitter_consumer_key(self):
        return self.config[self.TWITTER]['consumerkey']

    def read_twitter_consumer_secret(self):
        return self.config[self.TWITTER]['consumersecret']

    def read_twitter_access_token(self):
        return self.config[self.TWITTER]['accesstoken']

    def read_twitter_access_token_secret(self):
        return self.config[self.TWITTER]['accesstokensecret']

    def write_last_mention_id(self, id):
        """ Save to file the last mention id.
        :param id: last mention id
        :return:
        """
        self.config[self.CONFIGS]['lastmentionid'] = str(id)
        self._write()

    def _write(self):
        with open(self.settings_file, 'w') as configfile:
            self.config.write(configfile)

    NO_MENTIONS = 1
    def read_last_mention_id(self):
        try:
            return self.config[self.CONFIGS]['lastmentionid']
        except KeyError:
            return self.NO_MENTIONS

    def read_stopwords(self):
        stopwords = {}
        file_str = 'assets/stopwords-{0}.txt'
        langs = ['de', 'en', 'es', 'fr', 'it']
        for l in langs:
            stopwords[l] = {}
            with open(file_str.format(l), 'r') as f:
                for line in f.readlines():
                    stopwords[l][line[:-1]] = 1
        return stopwords

    def read_imgur_client_id(self):
        return self.config[self.IMGUR]['clientid']

    def read_imgur_client_secret(self):
        return self.config[self.IMGUR]['clientsecret']

    def read_imgur_access_token(self):
        return self.config[self.IMGUR]['accesstoken']

    def read_imgur_refresh_token(self):
        return self.config[self.IMGUR]['refreshtoken']

    def read_bot_name(self):
        return self.config[self.CONFIGS]['botname']

    def read_wordcloud_hashtag(self):
        return self.config[self.CONFIGS]['wordcloudhashtag']

    def read_max_words(self):
        return int(self.config[self.CONFIGS]['maxwords'])

    def read_output_dir(self):
        return self.config[self.CONFIGS]['outputdir']

    def read_max_results(self):
        return int(self.config[self.CONFIGS]['maxresults'])

    def read_width(self):
        return int(self.config[self.CONFIGS]['width'])

    def read_height(self):
        return int(self.config[self.CONFIGS]['height'])

    def read_description_image_str(self):
        return self.config[self.CONFIGS]['descriptionimagestr']