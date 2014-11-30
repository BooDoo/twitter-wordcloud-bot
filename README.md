Twitter Word Cloud Bot
======================

A Twitter bot that can build a word cloud image from the tweets of a Twitter user. The images are uploaded on Imgur.

You can see it in action [here](https://twitter.com/wordnuvola). If you want a word cloud for you Twitter account,
tweet "@wordnuvola #cloudword". If you want a word cloud for another Twitter accout, tweet
"@wordnuvola #cloudword @<other-twitter-account>". You should get an answer in the next few minutes if the bot is
online, otherwise you'll get it when the bot is turned on again.

You can see all the word clouds images made so far here http://defacto133.imgur.com/all/

The languages supported are English, French, German, Italian and Spanish (thanks to https://code.google.com/p/stop-words/).
For the other languages, stop words are not filtered so you probably are going to get the most common words in that language.

Requirements
------------

- Python >= 3.4 (I'm using Python 3.4, probably it works also with Python >= 3.0)
- [Python Twitter Tools](https://github.com/sixohsix/twitter)
- [word_cloud](https://github.com/amueller/word_cloud)
- [imgurpython](https://github.com/Imgur/imgurpython)

