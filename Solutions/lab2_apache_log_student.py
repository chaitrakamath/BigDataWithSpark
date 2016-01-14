{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "version 1.0.1\n",
    "#![Spark Logo](http://spark-mooc.github.io/web-assets/images/ta_Spark-logo-small.png) + ![Python Logo](http://spark-mooc.github.io/web-assets/images/python-logo-master-v3-TM-flattened_small.png)\n",
    "# **Web Server Log Analysis with Apache Spark**\n",
    " \n",
    "####This lab will demonstrate how easy it is to perform web server log analysis with Apache Spark.\n",
    " \n",
    "####Server log analysis is an ideal use case for Spark.  It's a very large, common data source and contains a rich set of information.  Spark allows you to store your logs in files on disk cheaply, while still providing a quick and simple way to perform data analysis on them.  This homework will show you how to use Apache Spark on real-world text-based production logs and fully harness the power of that data.  Log data comes from many sources, such as web, file, and compute servers, application logs, user-generated content,  and can be used for monitoring servers, improving business and customer intelligence, building recommendation systems, fraud detection, and much more."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "### How to complete this assignment\n",
    " \n",
    "####This assignment is broken up into sections with bite-sized examples for demonstrating Spark functionality for log processing. For each problem, you should start by thinking about the algorithm that you will use to *efficiently* process the log in a parallel, distributed manner. This means using the various [RDD](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD) operations along with [`lambda` functions](https://docs.python.org/2/tutorial/controlflow.html#lambda-expressions) that are applied at each worker.\n",
    " \n",
    "####This assignment consists of 4 parts:\n",
    "#### *Part 1*: Apache Web Server Log file format\n",
    "#### *Part 2*: Sample Analyses on the Web Server Log File\n",
    "#### *Part 3*: Analyzing Web Server Log File\n",
    "#### *Part 4*: Exploring 404 Response Codes"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "### **Part 1: Apache Web Server Log file format**\n",
    "####The log files that we use for this assignment are in the [Apache Common Log Format (CLF)](http://httpd.apache.org/docs/1.3/logs.html#common). The log file entries produced in CLF will look something like this:\n",
    "`127.0.0.1 - - [01/Aug/1995:00:00:01 -0400] \"GET /images/launch-logo.gif HTTP/1.0\" 200 1839`\n",
    " \n",
    "####Each part of this log entry is described below.\n",
    "* `127.0.0.1`\n",
    "####This is the IP address (or host name, if available) of the client (remote host) which made the request to the server.\n",
    " \n",
    "* `-`\n",
    "####The \"hyphen\" in the output indicates that the requested piece of information (user identity from remote machine) is not available.\n",
    " \n",
    "* `-`\n",
    "####The \"hyphen\" in the output indicates that the requested piece of information (user identity from local logon) is not available.\n",
    " \n",
    "* `[01/Aug/1995:00:00:01 -0400]`\n",
    "####The time that the server finished processing the request. The format is:\n",
    "`[day/month/year:hour:minute:second timezone]`\n",
    "  * ####day = 2 digits\n",
    "  * ####month = 3 letters\n",
    "  * ####year = 4 digits\n",
    "  * ####hour = 2 digits\n",
    "  * ####minute = 2 digits\n",
    "  * ####second = 2 digits\n",
    "  * ####zone = (\\+ | \\-) 4 digits\n",
    " \n",
    "* `\"GET /images/launch-logo.gif HTTP/1.0\"`\n",
    "####This is the first line of the request string from the client. It consists of a three components: the request method (e.g., `GET`, `POST`, etc.), the endpoint (a [Uniform Resource Identifier](http://en.wikipedia.org/wiki/Uniform_resource_identifier)), and the client protocol version.\n",
    " \n",
    "* `200`\n",
    "####This is the status code that the server sends back to the client. This information is very valuable, because it reveals whether the request resulted in a successful response (codes beginning in 2), a redirection (codes beginning in 3), an error caused by the client (codes beginning in 4), or an error in the server (codes beginning in 5). The full list of possible status codes can be found in the HTTP specification ([RFC 2616](https://www.ietf.org/rfc/rfc2616.txt) section 10).\n",
    " \n",
    "* `1839`\n",
    "####The last entry indicates the size of the object returned to the client, not including the response headers. If no content was returned to the client, this value will be \"-\" (or sometimes 0).\n",
    " \n",
    "####Note that log files contain information supplied directly by the client, without escaping. Therefore, it is possible for malicious clients to insert control-characters in the log files, *so care must be taken in dealing with raw logs.*\n",
    " \n",
    "### NASA-HTTP Web Server Log\n",
    "####For this assignment, we will use a data set from NASA Kennedy Space Center WWW server in Florida. The full data set is freely available (http://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html) and contains two month's of all HTTP requests. We are using a subset that only contains several days worth of requests."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "### **(1a) Parsing Each Log Line**\n",
    "####Using the CLF as defined above, we create a regular expression pattern to extract the nine fields of the log line using the Python regular expression [`search` function](https://docs.python.org/2/library/re.html#regular-expression-objects). The function returns a pair consisting of a Row object and 1. If the log line fails to match the regular expression, the function returns a pair consisting of the log line string and 0. A '-' value in the content size field is cleaned up by substituting it with 0. The function converts the log line's date string into a Python `datetime` object using the given `parse_apache_time` function."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 1,
   "metadata": {
    "collapsed": false
   },
   "outputs": [],
   "source": [
    "import re\n",
    "import datetime\n",
    "\n",
    "from pyspark.sql import Row\n",
    "\n",
    "month_map = {'Jan': 1, 'Feb': 2, 'Mar':3, 'Apr':4, 'May':5, 'Jun':6, 'Jul':7,\n",
    "    'Aug':8,  'Sep': 9, 'Oct':10, 'Nov': 11, 'Dec': 12}\n",
    "\n",
    "def parse_apache_time(s):\n",
    "    \"\"\" Convert Apache time format into a Python datetime object\n",
    "    Args:\n",
    "        s (str): date and time in Apache time format\n",
    "    Returns:\n",
    "        datetime: datetime object (ignore timezone for now)\n",
    "    \"\"\"\n",
    "    return datetime.datetime(int(s[7:11]),\n",
    "                             month_map[s[3:6]],\n",
    "                             int(s[0:2]),\n",
    "                             int(s[12:14]),\n",
    "                             int(s[15:17]),\n",
    "                             int(s[18:20]))\n",
    "\n",
    "\n",
    "def parseApacheLogLine(logline):\n",
    "    \"\"\" Parse a line in the Apache Common Log format\n",
    "    Args:\n",
    "        logline (str): a line of text in the Apache Common Log format\n",
    "    Returns:\n",
    "        tuple: either a dictionary containing the parts of the Apache Access Log and 1,\n",
    "               or the original invalid log line and 0\n",
    "    \"\"\"\n",
    "    match = re.search(APACHE_ACCESS_LOG_PATTERN, logline)\n",
    "    if match is None:\n",
    "        return (logline, 0)\n",
    "    size_field = match.group(9)\n",
    "    if size_field == '-':\n",
    "        size = long(0)\n",
    "    else:\n",
    "        size = long(match.group(9))\n",
    "    return (Row(\n",
    "        host          = match.group(1),\n",
    "        client_identd = match.group(2),\n",
    "        user_id       = match.group(3),\n",
    "        date_time     = parse_apache_time(match.group(4)),\n",
    "        method        = match.group(5),\n",
    "        endpoint      = match.group(6),\n",
    "        protocol      = match.group(7),\n",
    "        response_code = int(match.group(8)),\n",
    "        content_size  = size\n",
    "    ), 1)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 2,
   "metadata": {
    "collapsed": false
   },
   "outputs": [],
   "source": [
    "# A regular expression pattern to extract fields from the log line\n",
    "APACHE_ACCESS_LOG_PATTERN = '^(\\S+) (\\S+) (\\S+) \\[([\\w:/]+\\s[+\\-]\\d{4})\\] \"(\\S+) (\\S+)\\s*(\\S*)\" (\\d{3}) (\\S+)'"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "### **(1b) Configuration and Initial RDD Creation**\n",
    "####We are ready to specify the input log file and create an RDD containing the parsed log file data. The log file has already been downloaded for you.\n",
    " \n",
    "####To create the primary RDD that we'll use in the rest of this assignment, we first load the text file using [`sc.textfile(logFile)`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.SparkContext.textFile) to convert each line of the file into an element in an RDD.\n",
    "####Next, we use [`map(parseApacheLogLine)`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD.map) to apply the parse function to each element (that is, a line from the log file) in the RDD and turn each line into a pair [`Row` object](http://spark.apache.org/docs/latest/api/python/pyspark.sql.html#pyspark.sql.Row).\n",
    "####Finally, we cache the RDD in memory since we'll use it throughout this notebook."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 3,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Number of invalid logline: 108\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:43:39 -0400] \"GET / HTTP/1.0 \" 200 7131\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:43:57 -0400] \"GET /images/ksclogo-medium.gif HTTP/1.0 \" 200 5866\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:44:07 -0400] \"GET /images/NASA-logosmall.gif HTTP/1.0 \" 200 786\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:44:11 -0400] \"GET /images/MOSAIC-logosmall.gif HTTP/1.0 \" 200 363\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:44:13 -0400] \"GET /images/USA-logosmall.gif HTTP/1.0 \" 200 234\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:44:15 -0400] \"GET /images/WORLD-logosmall.gif HTTP/1.0 \" 200 669\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:44:31 -0400] \"GET /shuttle/countdown/ HTTP/1.0 \" 200 4673\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:44:41 -0400] \"GET /shuttle/missions/sts-69/count69.gif HTTP/1.0 \" 200 46053\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:45:34 -0400] \"GET /images/KSC-logosmall.gif HTTP/1.0 \" 200 1204\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:45:46 -0400] \"GET /cgi-bin/imagemap/countdown69?293,287 HTTP/1.0 \" 302 85\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:45:48 -0400] \"GET /htbin/cdt_main.pl HTTP/1.0 \" 200 3714\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:45:52 -0400] \"GET /shuttle/countdown/images/countclock.gif HTTP/1.0 \" 200 13994\n",
      "Invalid logline: ix-li1-14.ix.netcom.com - - [08/Aug/1995:14:46:22 -0400] \"GET / HTTP/1.0 \" 200 7131\n",
      "Invalid logline: ix-li1-14.ix.netcom.com - - [08/Aug/1995:14:46:29 -0400] \"GET /images/ksclogo-medium.gif HTTP/1.0 \" 200 5866\n",
      "Invalid logline: ix-li1-14.ix.netcom.com - - [08/Aug/1995:14:46:35 -0400] \"GET /images/NASA-logosmall.gif HTTP/1.0 \" 200 786\n",
      "Invalid logline: ix-li1-14.ix.netcom.com - - [08/Aug/1995:14:46:37 -0400] \"GET /images/MOSAIC-logosmall.gif HTTP/1.0 \" 200 363\n",
      "Invalid logline: ix-li1-14.ix.netcom.com - - [08/Aug/1995:14:46:38 -0400] \"GET /images/USA-logosmall.gif HTTP/1.0 \" 200 234\n",
      "Invalid logline: ix-li1-14.ix.netcom.com - - [08/Aug/1995:14:46:40 -0400] \"GET /images/WORLD-logosmall.gif HTTP/1.0 \" 200 669\n",
      "Invalid logline: ix-li1-14.ix.netcom.com - - [08/Aug/1995:14:47:41 -0400] \"GET /shuttle/missions/sts-70/mission-sts-70.html HTTP/1.0 \" 200 20304\n",
      "Invalid logline: ix-sac6-20.ix.netcom.com - - [08/Aug/1995:14:47:48 -0400] \"GET /shuttle/countdown/count.html HTTP/1.0 \" 200 73231\n",
      "Read 1043177 lines, successfully parsed 1043069 lines, failed to parse 108 lines\n"
     ]
    }
   ],
   "source": [
    "import sys\n",
    "import os\n",
    "from test_helper import Test\n",
    "\n",
    "baseDir = os.path.join('data')\n",
    "inputPath = os.path.join('cs100', 'lab2', 'apache.access.log.PROJECT')\n",
    "logFile = os.path.join(baseDir, inputPath)\n",
    "\n",
    "def parseLogs():\n",
    "    \"\"\" Read and parse log file \"\"\"\n",
    "    parsed_logs = (sc\n",
    "                   .textFile(logFile)\n",
    "                   .map(parseApacheLogLine)\n",
    "                   .cache())\n",
    "\n",
    "    access_logs = (parsed_logs\n",
    "                   .filter(lambda s: s[1] == 1)\n",
    "                   .map(lambda s: s[0])\n",
    "                   .cache())\n",
    "\n",
    "    failed_logs = (parsed_logs\n",
    "                   .filter(lambda s: s[1] == 0)\n",
    "                   .map(lambda s: s[0]))\n",
    "    failed_logs_count = failed_logs.count()\n",
    "    if failed_logs_count > 0:\n",
    "        print 'Number of invalid logline: %d' % failed_logs.count()\n",
    "        for line in failed_logs.take(20):\n",
    "            print 'Invalid logline: %s' % line\n",
    "\n",
    "    print 'Read %d lines, successfully parsed %d lines, failed to parse %d lines' % (parsed_logs.count(), access_logs.count(), failed_logs.count())\n",
    "    return parsed_logs, access_logs, failed_logs\n",
    "\n",
    "\n",
    "parsed_logs, access_logs, failed_logs = parseLogs()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "### **(1c) Data Cleaning**\n",
    "#### Notice that there are a large number of log lines that failed to parse. Examine the sample of invalid lines and compare them to the correctly parsed line, an example is included below. Based on your observations, alter the `APACHE_ACCESS_LOG_PATTERN` regular expression below so that the failed lines will correctly parse, and press `Shift-Enter` to rerun `parseLogs()`.\n",
    " \n",
    "`127.0.0.1 - - [01/Aug/1995:00:00:01 -0400] \"GET /images/launch-logo.gif HTTP/1.0\" 200 1839`\n",
    " \n",
    "#### If you not familar with Python regular expression [`search` function](https://docs.python.org/2/library/re.html#regular-expression-objects), now would be a good time to check up on the [documentation](https://developers.google.com/edu/python/regular-expressions). One tip that might be useful is to use an online tester like http://pythex.org or http://www.pythonregex.com. To use it, copy and paste the regular expression string below (located between the single quotes ') and test it against one of the 'Invalid logline' above."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 4,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Read 1043177 lines, successfully parsed 1043177 lines, failed to parse 0 lines\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "# This was originally '^(\\S+) (\\S+) (\\S+) \\[([\\w:/]+\\s[+\\-]\\d{4})\\] \"(\\S+) (\\S+)\\s*(\\S*)\" (\\d{3}) (\\S+)'\n",
    "APACHE_ACCESS_LOG_PATTERN = '^(\\S+) (\\S+) (\\S+) \\[([\\w:/]+\\s[+\\-]\\d{4})\\] \"(\\S+) (\\S+)\\s*(\\S*)\\s*\" (\\d{3}) (\\S+)'\n",
    "\n",
    "parsed_logs, access_logs, failed_logs = parseLogs()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 6,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Data cleaning (1c)\n",
    "Test.assertEquals(failed_logs.count(), 0, 'incorrect failed_logs.count()')\n",
    "Test.assertEquals(parsed_logs.count(), 1043177 , 'incorrect parsed_logs.count()')\n",
    "Test.assertEquals(access_logs.count(), parsed_logs.count(), 'incorrect access_logs.count()')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "### **Part 2: Sample Analyses on the Web Server Log File**\n",
    " \n",
    "####Now that we have an RDD containing the log file as a set of Row objects, we can perform various analyses.\n",
    " \n",
    "#### **(2a) Example: Content Size Statistics**\n",
    " \n",
    "####Let's compute some statistics about the sizes of content being returned by the web server. In particular, we'd like to know what are the average, minimum, and maximum content sizes.\n",
    " \n",
    "####We can compute the statistics by applying a `map` to the `access_logs` RDD. The `lambda` function we want for the map is to extract the `content_size` field from the RDD. The map produces a new RDD containing only the `content_sizes` (one element for each Row object in the `access_logs` RDD). To compute the minimum and maximum statistics, we can use [`min()`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD.min) and [`max()`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD.max) functions on the new RDD. We can compute the average statistic by using the [`reduce`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD.reduce) function with a `lambda` function that sums the two inputs, which represent two elements from the new RDD that are being reduced together. The result of the `reduce()` is the total content size from the log and it is to be divided by the number of requests as determined using the [`count()`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD.count) function on the new RDD."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 7,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Content Size Avg: 17531, Min: 0, Max: 3421948\n"
     ]
    }
   ],
   "source": [
    "# Calculate statistics based on the content size.\n",
    "content_sizes = access_logs.map(lambda log: log.content_size).cache()\n",
    "print 'Content Size Avg: %i, Min: %i, Max: %s' % (\n",
    "    content_sizes.reduce(lambda a, b : a + b) / content_sizes.count(),\n",
    "    content_sizes.min(),\n",
    "    content_sizes.max())"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(2b) Example: Response Code Analysis**\n",
    "####Next, lets look at the response codes that appear in the log. As with the content size analysis, first we create a new RDD by using a `lambda` function to extract the `response_code` field from the `access_logs` RDD. The difference here is that we will use a [pair tuple](https://docs.python.org/2/tutorial/datastructures.html?highlight=tuple#tuples-and-sequences) instead of just the field itself. Using a pair tuple consisting of the response code and 1 will let us count how many records have a particular response code. Using the new RDD, we perform a [`reduceByKey`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD.reduceByKey) function. `reduceByKey` performs a reduce on a per-key basis by applying the `lambda` function to each element, pairwise with the same key. We use the simple `lambda` function of adding the two values. Then, we cache the resulting RDD and create a list by using the [`take`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD.take) function."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 8,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Found 7 response codes\n",
      "Response Code Counts: [(200, 940847), (304, 79824), (404, 6185), (500, 2), (501, 17), (302, 16244), (403, 58)]\n"
     ]
    }
   ],
   "source": [
    "# Response Code to Count\n",
    "responseCodeToCount = (access_logs\n",
    "                       .map(lambda log: (log.response_code, 1))\n",
    "                       .reduceByKey(lambda a, b : a + b)\n",
    "                       .cache())\n",
    "responseCodeToCountList = responseCodeToCount.take(100)\n",
    "print 'Found %d response codes' % len(responseCodeToCountList)\n",
    "print 'Response Code Counts: %s' % responseCodeToCountList\n",
    "assert len(responseCodeToCountList) == 7\n",
    "assert sorted(responseCodeToCountList) == [(200, 940847), (302, 16244), (304, 79824), (403, 58), (404, 6185), (500, 2), (501, 17)]"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(2c) Example: Response Code Graphing with `matplotlib`**\n",
    "####Now, lets visualize the results from the last example. We can visualize the results from the last example using [`matplotlib`](http://matplotlib.org/). First we need to extract the labels and fractions for the graph. We do this with two separate `map` functions with a `lambda` functions. The first `map` function extracts a list of of the response code values, and the second `map` function extracts a list of the per response code counts  divided by the total size of the access logs. Next, we create a figure with `figure()` constructor and use the `pie()` method to create the pie plot."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 9,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "[200, 304, 404, 500, 501, 302, 403]\n",
      "[0.9019054292799784, 0.07652009198822443, 0.005929003419362198, 1.9172201841106543e-06, 1.629637156494056e-05, 0.015571662335346735, 5.5599385339208974e-05]\n"
     ]
    }
   ],
   "source": [
    "labels = responseCodeToCount.map(lambda (x, y): x).collect()\n",
    "print labels\n",
    "count = access_logs.count()\n",
    "fracs = responseCodeToCount.map(lambda (x, y): (float(y) / count)).collect()\n",
    "print fracs"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 18,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "ename": "NameError",
     "evalue": "name 'fracs' is not defined",
     "output_type": "error",
     "traceback": [
      "\u001b[1;31m---------------------------------------------------------------------------\u001b[0m",
      "\u001b[1;31mNameError\u001b[0m                                 Traceback (most recent call last)",
      "\u001b[1;32m<ipython-input-18-1cbdefef6251>\u001b[0m in \u001b[0;36m<module>\u001b[1;34m()\u001b[0m\n\u001b[0;32m     14\u001b[0m \u001b[0mcolors\u001b[0m \u001b[1;33m=\u001b[0m \u001b[1;33m[\u001b[0m\u001b[1;34m'yellowgreen'\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;34m'lightskyblue'\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;34m'gold'\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;34m'purple'\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;34m'lightcoral'\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;34m'yellow'\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;34m'black'\u001b[0m\u001b[1;33m]\u001b[0m\u001b[1;33m\u001b[0m\u001b[0m\n\u001b[0;32m     15\u001b[0m \u001b[0mexplode\u001b[0m \u001b[1;33m=\u001b[0m \u001b[1;33m(\u001b[0m\u001b[1;36m0.05\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;36m0.05\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;36m0.1\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;36m0\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;36m0\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;36m0\u001b[0m\u001b[1;33m,\u001b[0m \u001b[1;36m0\u001b[0m\u001b[1;33m)\u001b[0m\u001b[1;33m\u001b[0m\u001b[0m\n\u001b[1;32m---> 16\u001b[1;33m patches, texts, autotexts = plt.pie(fracs, labels=labels, colors=colors,\n\u001b[0m\u001b[0;32m     17\u001b[0m                                     \u001b[0mexplode\u001b[0m\u001b[1;33m=\u001b[0m\u001b[0mexplode\u001b[0m\u001b[1;33m,\u001b[0m \u001b[0mautopct\u001b[0m\u001b[1;33m=\u001b[0m\u001b[0mpie_pct_format\u001b[0m\u001b[1;33m,\u001b[0m\u001b[1;33m\u001b[0m\u001b[0m\n\u001b[0;32m     18\u001b[0m                                     shadow=False,  startangle=125)\n",
      "\u001b[1;31mNameError\u001b[0m: name 'fracs' is not defined"
     ]
    },
    {
     "data": {
      "text/plain": [
       "<matplotlib.figure.Figure at 0xb0609b4c>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "import matplotlib.pyplot as plt\n",
    "\n",
    "\n",
    "def pie_pct_format(value):\n",
    "    \"\"\" Determine the appropriate format string for the pie chart percentage label\n",
    "    Args:\n",
    "        value: value of the pie slice\n",
    "    Returns:\n",
    "        str: formated string label; if the slice is too small to fit, returns an empty string for label\n",
    "    \"\"\"\n",
    "    return '' if value < 7 else '%.0f%%' % value\n",
    "\n",
    "fig = plt.figure(figsize=(4.5, 4.5), facecolor='white', edgecolor='white')\n",
    "colors = ['yellowgreen', 'lightskyblue', 'gold', 'purple', 'lightcoral', 'yellow', 'black']\n",
    "explode = (0.05, 0.05, 0.1, 0, 0, 0, 0)\n",
    "patches, texts, autotexts = plt.pie(fracs, labels=labels, colors=colors,\n",
    "                                    explode=explode, autopct=pie_pct_format,\n",
    "                                    shadow=False,  startangle=125)\n",
    "for text, autotext in zip(texts, autotexts):\n",
    "    if autotext.get_text() == '':\n",
    "        text.set_text('')  # If the slice is small to fit, don't show a text label\n",
    "plt.legend(labels, loc=(0.80, -0.1), shadow=True)\n",
    "pass"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(2d) Example: Frequent Hosts**\n",
    "####Let's look at hosts that have accessed the server multiple times (e.g., more than ten times). As with the response code analysis in (2b), first we create a new RDD by using a `lambda` function to extract the `host` field from the `access_logs` RDD using a pair tuple consisting of the host and 1 which will let us count how many records were created by a particular host's request. Using the new RDD, we perform a `reduceByKey` function with a `lambda` function that adds the two values. We then filter the result based on the count of accesses by each host (the second element of each pair) being greater than ten. Next, we extract the host name by performing a `map` with a `lambda` function that returns the first element of each pair. Finally, we extract 20 elements from the resulting RDD - *note that the choice of which elements are returned is not guaranteed to be deterministic.*"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 11,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Any 20 hosts that have accessed more then 10 times: [u'slip3.nilenet.com', u'client-71-31.online.apple.com', u'ix-jac2-16.ix.netcom.com', u'slip124.qlink.queensu.ca', u'ppp0e-01.rns.tamu.edu', u'ix-ftl2-16.ix.netcom.com', u'202.40.17.51', u'dialin14.wantree.com.au', u'y1a.kootenay.net', u'199.242.22.79', u'133.65.48.113', u'weird.stardust.com', u'ucsdtv2.ucsd.edu', u'dialup2.speed.net', u'147.150.5.96', u'pc-117.grassroots.ns.ca', u'152.52.29.20', u'asyn01.lw2.noord.bart.nl', u'bilbo.klautern.fh-rpl.de', u'cywilli.psdn177.pacbell.com']\n"
     ]
    }
   ],
   "source": [
    "# Any hosts that has accessed the server more than 10 times.\n",
    "hostCountPairTuple = access_logs.map(lambda log: (log.host, 1))\n",
    "\n",
    "hostSum = hostCountPairTuple.reduceByKey(lambda a, b : a + b)\n",
    "\n",
    "hostMoreThan10 = hostSum.filter(lambda s: s[1] > 10)\n",
    "\n",
    "hostsPick20 = (hostMoreThan10\n",
    "               .map(lambda s: s[0])\n",
    "               .take(20))\n",
    "\n",
    "print 'Any 20 hosts that have accessed more then 10 times: %s' % hostsPick20\n",
    "# An example: [u'204.120.34.185', u'204.243.249.9', u'slip1-32.acs.ohio-state.edu', u'lapdog-14.baylor.edu', u'199.77.67.3', u'gs1.cs.ttu.edu', u'haskell.limbex.com', u'alfred.uib.no', u'146.129.66.31', u'manaus.bologna.maraut.it', u'dialup98-110.swipnet.se', u'slip-ppp02.feldspar.com', u'ad03-053.compuserve.com', u'srawlin.opsys.nwa.com', u'199.202.200.52', u'ix-den7-23.ix.netcom.com', u'151.99.247.114', u'w20-575-104.mit.edu', u'205.25.227.20', u'ns.rmc.com']"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(2e) Example: Visualizing Endpoints**\n",
    "####Now, lets visualize the number of hits to endpoints (URIs) in the log. To perform this task, we first create a new RDD by using a `lambda` function to extract the `endpoint` field from the `access_logs` RDD using a pair tuple consisting of the endpoint and 1 which will let us count how many records were created by a particular host's request. Using the new RDD, we perform a `reduceByKey` function with a `lambda` function that adds the two values. We then cache the results.\n",
    " \n",
    "####Next we visualize the results using `matplotlib`. We previously imported the `matplotlib.pyplot` library, so we do not need to import it again. We perform two separate `map` functions with `lambda` functions. The first `map` function extracts a list of endpoint values, and the second `map` function extracts a list of the visits per endpoint values. Next, we create a figure with `figure()` constructor, set various features of the plot (axis limits, grid lines, and labels), and use the `plot()` method to create the line plot."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 12,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "data": {
      "image/png": "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\nBwxxcXEe2yw734rmX9FBiCQNHDhQdrvd5S8pKclljLgkbdmyRXa73e31EydO1NKlS13KcnNzZbfb\nderUKZfyp556SgsXLnQpy8/Pl91uV15enkv54sWLNXnyZJey8+fPy26364MPPnApX7VqVbl3l7n/\n/vu9Xg5poj75xH05Nm60Swqd5QiX7VHV5TCMfEmhvxzhsj3CfTmk8FiOUN0eZ8+Gx3KEy/ZgOSq/\nHKtWrXLmYs2bN1f79u2VkZHh1k6VGVXw1ltvGS1btjRsNpuRkpJifPrpp5Vu6+mnnzZsNpvxzDPP\nuE27fPmyER0dbYwfP95tWv/+/Y2EhATn85UrVxo2m834+OOPXeoVFBQYNpvNmD9/vrMsJSXFaN26\ntVub8+fPN2w2m1FQUGAYhmEcO3bMsNlsxsKFC93qJiQkGP379/e4XDk5OYYkIycnx2OdSLF2rWFI\nhjFnjvnYsWPptAkTzLLc3MDFB99Vq2ZuN3gnOtq79fXtt2a9lBT/xxQqzH5U69pLSTHbO3vWujYd\nrI41WPziF+ZyVWFXDwQtf+RrlbrwcceOHerSpYseeOAB3XjjjdqyZYvee+89tW/fvlKJ/q9+9SvN\nnj1bs2bN0qxZs9ym16hRQ2lpaVq7dq3OnTvnLM/Pz9f27ds1ePBgZ1lqaqqioqK0fPlylzaWL18u\nm82m++67z1k2aNAg5eXlac+ePc6y4uJirVixQt26dVOjRo0kSU2aNFGXLl20YsUKlZSUOOvu3r1b\nBw8edJk/AFiF0/MAELp8uk/2vn37NHXqVL333ntq3ry5Vq5cqQceeKBKATz33HN66qmnlJqaqoED\nB7rcm1qSunXrJskcStK5c2fde++9mjZtmvPHaBo0aKDHH3/cWT8mJkYzZ87UrFmzFBsbq379+umT\nTz7R7NmzNWbMGCUmJjrrjh49WllZWRo2bJgWLFig+Ph4vfzyyzp06JCys7Nd4li4cKH69eunYcOG\nafz48Tpx4oSmTZumNm3aePyBHgCoDJJrAAh9XiXZ+fn5mjlzplauXKm4uDi98MILGjdunGrWrFnl\nADZs2CCbzabNmzdr8+bNLtNsNpuuXLkiSUpISNCOHTs0depUDR06VDVq1FBycrIWLVrkNib6ySef\nVL169ZSVlaVFixapcePGmj59uvNuJQ61atXS1q1bNWXKFE2aNEnnz59Xhw4dtGnTJvXs2dOlbq9e\n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\nX3nqYfyf/zHbGz7cu8/vq6+aj473XnnfhVOmSAMHmomQp6/mig7g/vIXafHiiuMpKyZGeuyx0ueO\nz9eSmN0AABwQSURBVKO3yUlFfv1r6e23V2nKlMq38ac/uQ4jMozS/VJxcWlidOqU5x53b1jx3bBv\nnzm0wZehlA6O99v69aW3FSwbV0mJeQ3DF194bmPJEmndutKDH8d7rbjYjC052dw3lf3uqsx38JEj\nvr/GXxzfSWUP+BwHnOUdDF9L8+be1XOss2vtgypSUOD6ma4oJ7teSLJ9sHHjRmVnZ2vJkiUaM2aM\nevXqpT/84Q/q16+fJk+erJJrDPJaulQaN670whGHy5elX/2q9LnjqP/nPy/tVT1yRJo3z/V1Vb0Y\n6/Dhqr2+PI88Yh7xlv2SOXCg4gsyUlOll1+uuP0bbzR3nOXdF9uxEyt7EHPokOe2rk6yHa8vm+zM\nn++6bcoyDGvWYVXvxXzlinc9ueWNOS4pce3huZayFxLl5l677tixUqNG7vOfOvXaryv7pegYO75l\ni9Sxo3xOKnbu9G69XCuRrmyS8Mtfmj2w3uxsa9QwH8uegfntb80Da299/711vWmPPGI+Or6nJkxY\npXHjXN+fp06Z89u2zbzA2ls/+EH55Y5E7k9/8m7Yz5gx5vu+orG1JSVme45lupojdsMof5jUokXm\na725k1NZ77xT+r+nz0rVEtBVHg86vVX2YKZaNbOXsmlT86CkeXNz3cXHSzfdVLX5eHKtz0ZeXunt\nTx3fT46zEjabtH+/+R5wtPHaa2aie61hIo7l3bq1dP+xcqU0fbp73c8/Lx0+8O9/u05zJNlXv+eq\nkmSvXy/dfnvlE0xPZ1wMw7wuo+wBshVKSqz7vrFquMi335oH/927l5aRZIegdevWqV69eho2bJhL\neXp6uv7973/r448/9vjaJUvMx6t3/H/+s2tvadkvX8c4NKl0fJPj0VNyZBjmF3tFPeZZWdJDD3ke\ng/vNN2Zi42kH9s035fe23XefeSGaw113mUf7ZZOIisbMXcumTVKXLtKaNeX3Mpdd7mutg+Jic3zf\n1acIL18217uni8J+8xupc2fzKu2WLUt7LA3D7C0pO09vxjdfqzfOG2PGSHXrmjseRxzffOO+0xk+\n3P21v/qVFBdnJrIjR5aWX6tnRypNHMr7YmzWTHrlFff3xtChrsNkHJ5+Wpo921wPZYdM9O1b+v+1\nvoCv7lkxDHMsb+/e5vAfTxzb+eoku+y8rpUIDRjg+eDRcaHktYYuOTjOwJSt++GHFb+urBtvNLd3\nWeWtsw8+MO9TLXl+vzm+X8re433TpvK/B5KTXXdqZef9/ffm59PX93WfPu5lq1a5z//ixYo/O44e\n2YoOYJcuNYdJeerZnjDB9bu4Ir5+B0hmUuepF/9aSX6NGu4dN5I0Y4Z08KDn15W3Tr7+2rzAUKq4\nZ/XCBWnYMNczf45rigyj4mF35b0/168333etW0vdupmfI8d+zrFuDMP8znv11dLPzOjRZtLn6SBO\nKq370EOlZZMmlV/3jjvMM6iSVLNm+e1cvf6qkiQ6PnOOa1q++sp8b+/a5fk1JSXlz3PECPMgXzIP\nhteu9bycku8HkJK5D7z6++aDD8ofFiSZ+xd/+9nPzMf9+81t5Gnfbxhm/Nf1zl0GvNatWzeja9eu\nbuX79+83bDab8corr7hNy8nJMSQZUo4hGUbNmq7Tly0zDHPTu/89/7zr8337DOPBB0ufO/z2t57b\nqOhvwwazjT17DOOPfzSMS5cMY9Ikw7DbzenDhxtG27ZmnYsXDWPpUsMoKXGNYeZM1zYHDXKfz/33\nG8af/1xxPCtXGsaRI2a7lVmezz83jF27DGPhworqpjn/b9eutPyppzy/Zt++0v+nTTMft20zjJ/9\nzHU5e/Z0fV16urk8jtePHm0+f/bZ8ufjaO93vzPrlZQYxtdfm8vVvr353DAM45ln3F9bVGQYb75Z\n+v5xKFvHoXt3z8v6m98YxpIl116Hn35qGDfeWPE2MQzDaNXKdd6GYRiFha71GjVKM/bt87ztS0oM\n48MPDaN5c8/zcSx72b+5c0vneeiQ+R5/4onS93/Zuh99VFq3Wzf3dVZ2fbZoYRj5+eb/mzeX1nWs\n1zNnDCMvz7v37YwZhjFlitn24MGl5SkphvHNN+bn4sABw7l+DMNcjqvXoWQYzz1nfmYlw0hMdH8P\nGIbndXj1+pTSjLg4w2jSxCx78UX3eoWFZt133zXf/5JhjBljPm7fbk47fNj1NQMHmnXfe8+79XP1\n37//bbbx/7d370FRnecfwL9n5bYuqLCi3JoxAQlXB0wIwXRaYlAJFfEyEm3TAhkTo9jUXxKNSDRe\nEK+xVps4MdZ6QyWaTmJB0yJksRmlrZqpN2onCcXxhhfQcFfk+f2x3YV1l4u47K7x+5l5x933vOec\n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\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0xb0c0286c>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "endpoints = (access_logs\n",
    "             .map(lambda log: (log.endpoint, 1))\n",
    "             .reduceByKey(lambda a, b : a + b)\n",
    "             .cache())\n",
    "ends = endpoints.map(lambda (x, y): x).collect()\n",
    "counts = endpoints.map(lambda (x, y): y).collect()\n",
    "\n",
    "fig = plt.figure(figsize=(8,4.2), facecolor='white', edgecolor='white')\n",
    "plt.axis([0, len(ends), 0, max(counts)])\n",
    "plt.grid(b=True, which='major', axis='y')\n",
    "plt.xlabel('Endpoints')\n",
    "plt.ylabel('Number of Hits')\n",
    "plt.plot(counts)\n",
    "pass"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(2f) Example: Top Endpoints**\n",
    "####For the final example, we'll look at the top endpoints (URIs) in the log. To determine them, we first create a new RDD by using a `lambda` function to extract the `endpoint` field from the `access_logs` RDD using a pair tuple consisting of the endpoint and 1 which will let us count how many records were created by a particular host's request. Using the new RDD, we perform a `reduceByKey` function with a `lambda` function that adds the two values. We then extract the top ten endpoints by performing a [`takeOrdered`](http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD.takeOrdered) with a value of 10 and a `lambda` function that multiplies the count (the second element of each pair) by -1 to create a sorted list with the top endpoints at the bottom."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 13,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Top Ten Endpoints: [(u'/images/NASA-logosmall.gif', 59737), (u'/images/KSC-logosmall.gif', 50452), (u'/images/MOSAIC-logosmall.gif', 43890), (u'/images/USA-logosmall.gif', 43664), (u'/images/WORLD-logosmall.gif', 43277), (u'/images/ksclogo-medium.gif', 41336), (u'/ksc.html', 28582), (u'/history/apollo/images/apollo-logo1.gif', 26778), (u'/images/launch-logo.gif', 24755), (u'/', 20292)]\n"
     ]
    }
   ],
   "source": [
    "# Top Endpoints\n",
    "endpointCounts = (access_logs\n",
    "                  .map(lambda log: (log.endpoint, 1))\n",
    "                  .reduceByKey(lambda a, b : a + b))\n",
    "\n",
    "topEndpoints = endpointCounts.takeOrdered(10, lambda s: -1 * s[1])\n",
    "\n",
    "print 'Top Ten Endpoints: %s' % topEndpoints\n",
    "assert topEndpoints == [(u'/images/NASA-logosmall.gif', 59737), (u'/images/KSC-logosmall.gif', 50452), (u'/images/MOSAIC-logosmall.gif', 43890), (u'/images/USA-logosmall.gif', 43664), (u'/images/WORLD-logosmall.gif', 43277), (u'/images/ksclogo-medium.gif', 41336), (u'/ksc.html', 28582), (u'/history/apollo/images/apollo-logo1.gif', 26778), (u'/images/launch-logo.gif', 24755), (u'/', 20292)], 'incorrect Top Ten Endpoints'"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "### **Part 3: Analyzing Web Server Log File**\n",
    " \n",
    "####Now it is your turn to perform analyses on web server log files."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(3a) Exercise: Top Ten Error Endpoints**\n",
    "####What are the top ten endpoints which did not have return code 200? Create a sorted list containing top ten endpoints and the number of times that they were accessed with non-200 return code.\n",
    " \n",
    "####Think about the steps that you need to perform to determine which endpoints did not have a 200 return code, how you will uniquely count those endpoints, and sort the list.\n",
    " \n",
    "####You might want to refer back to the previous Lab (Lab 1 Word Count) for insights."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 23,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1043177\n",
      "7689\n",
      "Top Ten failed URLs: [(u'/images/NASA-logosmall.gif', 8761), (u'/images/KSC-logosmall.gif', 7236), (u'/images/MOSAIC-logosmall.gif', 5197), (u'/images/USA-logosmall.gif', 5157), (u'/images/WORLD-logosmall.gif', 5020), (u'/images/ksclogo-medium.gif', 4728), (u'/history/apollo/images/apollo-logo1.gif', 2907), (u'/images/launch-logo.gif', 2811), (u'/', 2199), (u'/images/ksclogosmall.gif', 1622)]\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "# HINT: Each of these <FILL IN> below could be completed with a single transformation or action.\n",
    "# You are welcome to structure your solution in a different way, so long as\n",
    "# you ensure the variables used in the next Test section are defined (ie. endpointSum, topTenErrURLs).\n",
    "\n",
    "not200 = (access_logs.filter(lambda log: log.response_code != 200).map(lambda log : log.endpoint))\n",
    "\n",
    "endpointCountPairTuple = not200.map(lambda s: (s, 1))\n",
    "                        \n",
    "endpointSum = endpointCountPairTuple.reduceByKey(lambda a, b : a + b)\n",
    "\n",
    "topTenErrURLs = endpointSum.takeOrdered(10, lambda s: -1 * s[1])\n",
    "print 'Top Ten failed URLs: %s' % topTenErrURLs\n",
    "\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 24,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Top ten error endpoints (3a)\n",
    "Test.assertEquals(endpointSum.count(), 7689, 'incorrect count for endpointSum')\n",
    "Test.assertEquals(topTenErrURLs, [(u'/images/NASA-logosmall.gif', 8761), (u'/images/KSC-logosmall.gif', 7236), (u'/images/MOSAIC-logosmall.gif', 5197), (u'/images/USA-logosmall.gif', 5157), (u'/images/WORLD-logosmall.gif', 5020), (u'/images/ksclogo-medium.gif', 4728), (u'/history/apollo/images/apollo-logo1.gif', 2907), (u'/images/launch-logo.gif', 2811), (u'/', 2199), (u'/images/ksclogosmall.gif', 1622)], 'incorrect Top Ten failed URLs (topTenErrURLs)')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(3b) Exercise: Number of Unique Hosts**\n",
    "####How many unique hosts are there in the entire log?\n",
    " \n",
    "####Think about the steps that you need to perform to count the number of different hosts in the log."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 32,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Unique hosts: 54507\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "# HINT: Do you recall the tips from (3a)? Each of these <FILL IN> could be an transformation or action.\n",
    "\n",
    "hosts = access_logs.map(lambda log: log.host)\n",
    "\n",
    "uniqueHosts = hosts.distinct()\n",
    "\n",
    "uniqueHostCount = uniqueHosts.count()\n",
    "print 'Unique hosts: %d' % uniqueHostCount\n",
    "\n",
    "\n",
    "\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 34,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Number of unique hosts (3b)\n",
    "Test.assertEquals(uniqueHostCount, 54507, 'incorrect uniqueHostCount')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(3c) Exercise: Number of Unique Daily Hosts**\n",
    "####For an advanced exercise, let's determine the number of unique hosts in the entire log on a day-by-day basis. This computation will give us counts of the number of unique daily hosts. We'd like a list sorted by increasing day of the month which includes the day of the month and the associated number of unique hosts for that day. Make sure you cache the resulting RDD `dailyHosts` so that we can reuse it in the next exercise.\n",
    " \n",
    "####Think about the steps that you need to perform to count the number of different hosts that make requests *each* day.\n",
    "####*Since the log only covers a single month, you can ignore the month.*"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 30,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "PythonRDD[172] at RDD at PythonRDD.scala:43\n",
      "Unique hosts per day: [(1, 2582), (3, 3222), (4, 4190), (5, 2502), (6, 2537), (7, 4106), (8, 4406), (9, 4317), (10, 4523), (11, 4346), (12, 2864), (13, 2650), (14, 4454), (15, 4214), (16, 4340), (17, 4385), (18, 4168), (19, 2550), (20, 2560), (21, 4134), (22, 4456)]\n"
     ]
    }
   ],
   "source": [
    "\n",
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "dayToHostPairTuple = access_logs.map(lambda log: (log.date_time.date().day, log.host)).groupByKey()\n",
    "\n",
    "dayGroupedHosts = dayToHostPairTuple.map(lambda x : (x[0], list(x[1])))\n",
    "\n",
    "dayHostCount = dayGroupedHosts.map(lambda (a, b) : (a,len(set(b))))\n",
    "\n",
    "\n",
    "dailyHosts = dayHostCount.sortByKey().cache()\n",
    "\n",
    "dailyHostsList = dailyHosts.take(30)\n",
    "print 'Unique hosts per day: %s' % dailyHostsList\n",
    "\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 14,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Number of unique daily hosts (3c)\n",
    "Test.assertEquals(dailyHosts.count(), 21, 'incorrect dailyHosts.count()')\n",
    "Test.assertEquals(dailyHostsList, [(1, 2582), (3, 3222), (4, 4190), (5, 2502), (6, 2537), (7, 4106), (8, 4406), (9, 4317), (10, 4523), (11, 4346), (12, 2864), (13, 2650), (14, 4454), (15, 4214), (16, 4340), (17, 4385), (18, 4168), (19, 2550), (20, 2560), (21, 4134), (22, 4456)], 'incorrect dailyHostsList')\n",
    "Test.assertTrue(dailyHosts.is_cached, 'incorrect dailyHosts.is_cached')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(3d) Exercise: Visualizing the Number of Unique Daily Hosts**\n",
    "####Using the results from the previous exercise, use `matplotlib` to plot a \"Line\" graph of the unique hosts requests by day.\n",
    "#### `daysWithHosts` should be a list of days and `hosts` should be a list of number of unique hosts for each corresponding day.\n",
    "#### * How could you convert a RDD into a list? See the [`collect()` method](http://spark.apache.org/docs/latest/api/python/pyspark.html?highlight=collect#pyspark.RDD.collect)*"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 15,
   "metadata": {
    "collapsed": false
   },
   "outputs": [],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "daysWithHosts = dailyHosts.map(lambda (x, y): x).collect()\n",
    "hosts = dailyHosts.map(lambda (x, y): y).collect()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 16,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Visualizing unique daily hosts (3d)\n",
    "test_days = range(1, 23)\n",
    "test_days.remove(2)\n",
    "Test.assertEquals(daysWithHosts, test_days, 'incorrect days')\n",
    "Test.assertEquals(hosts, [2582, 3222, 4190, 2502, 2537, 4106, 4406, 4317, 4523, 4346, 2864, 2650, 4454, 4214, 4340, 4385, 4168, 2550, 2560, 4134, 4456], 'incorrect hosts')"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 19,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "data": {
      "image/png": "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\nYmNjkZWVVWp7fHw8Jk2aVGrb5cuXERsbi+3bt5favmLFijL11gDw6KOP8jx4HjwPngfPg+fB8+B5\nuMV5rFixwp6LtWrVCp06dUJcXFyZ41TI6VP8Kumvf/2rMplMavbs2WU+d/XqVVWvXj01bty4Mp+z\nWCwqLCzM/vHy5cuVyWRSaWlppfbLyclRJpNJzZs3z75twIABqk2bNmWOOW/ePGUymVROTk65sbLL\nBBEREZG+uVWXCQD429/+hlmzZmH69OmYPn16mc97e3tj4MCBWL16NS5dumTfnp2djeTkZAwZMsS+\nLSYmBr6+vliyZEmpYyxZsgQmkwmDBg2ybxs8eDCysrKwa9cu+zabzYZPP/0UkZGRCA0NdeBZEhER\nEZEeaV5D/M4772DmzJmIiYnBgw8+iJ07d5b6fGRkJAApp+jWrRsefvhhTJ06FVeuXMGMGTMQHByM\nV155xb6/v78/pk2bhunTpyMgIAD9+/fH7t27MWvWLDzzzDMIDw+37ztmzBgkJCRg+PDhmD9/PoKC\ngrBw4UIcPnwYSUlJrvkPICIiIiJNaZ4Qr1+/HiaTCYmJiUhMTCz1OZPJhGvXrgEAwsLCsHnzZkyZ\nMgXDhg2Dt7c3+vbti7fffrtMre9rr72GBg0aICEhAW+//TYaN26MV1991d61oljt2rVhtVoxefJk\nTJw4EZcvX0bnzp2xYcMG9OrVy7knTkRERES6YFJKKa2DcDcZGRno2rUr0tPT0aVLF63DISIiIqIb\nVCVf00UNMRERERGRVpgQExEREZGhMSEmIiIiIkNjQkxEREREhsaEmIiIiIgMjQkxERERERkaE2Ii\nIiIiMjQmxERERERkaEyIiYiIiMjQmBATERERkaExISYiIiIiQ2NCTERERESGxoSYiIiIiAyNCTER\nERERGRoTYiIiIiIyNCbERERERGRoTIiJiIiIyNCYEBMRERGRoTEhJiIiIiJDY0JMRERERIbGhJiI\niIiIDI0JMREREREZGhNiIiIiIjI0JsREREREZGhMiImIiIjI0JgQExEREZGhMSEmIiIiIkNjQkxE\nREREhsaEmIiIiIgMjQkxERERERkaE2IiIiIiMjQmxERERERkaEyIiYiIiMjQmBATERERkaExISYi\nIiIiQ2NCTERERESGxoSYiIiIiAyNCTERERERGRoTYiIiIiIyNCbERERERGRoTIiJiIiIyNCYEBMR\n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\nADAa1xADAADAaARiAAAAGI1ADAAAAKMRiAEAAGA0AjEAAACMRiAGAACA0QjEAAAAMBqBGAAAAEYj\nEAMAAMBoBGIAqEcyMzPl4+PjeNlsNgUFBWngwIFKS0vTn3/+6ekSAcDrEIgBoB7KzMzU/v37tWPH\nDq1YsUKhoaFauHChQkJCtHPnTk+XBwBexWK32+2eLgIAUDsyMzM1fvx4HT58WOHh4U7Hfv31V/Xt\n21cXLlxQfn6+WrRo4aEqAcC7sEMMAIZ4+OGHtWTJEl26dEmrVq2SJB0+fFgvvviigoODdf/99ys4\nOFhjx45VYWGh43NnzpyR1WpVWlqayzn37t0rHx8fbdy40W3jAIDaRiAGAIM888wzatCggfbu3StJ\nOnv2rDp16qT33ntPubm5evfdd1VUVKQePXqopKREktSuXTtFR0dr5cqVqq6udjrf8uXL1bp1a40c\nOdLtYwGA2mL1dAEAAPfx9fVVYGCgioqKJEmxsbGKjY11HK+urtbQoUPVqlUrrV+/XlOnTpUkJSQk\nKDIyUlu2bNFzzz0nSTp37pw2b96slJQU+fiwvwKg7mIFAwDD3PrTkbKyMiUnJ6tDhw5q2LChrFar\nmjRpovLycp08edLRb8CAAerWrZvS09MdbStXrpSPj48mTZrk1voBoLYRiAHAIOXl5SopKdGDDz4o\nSRo7dqzS09M1adIk5ebm6tChQzp06JCaN2+uiooKp8++/vrr2rlzp/Lz83Xt2jWtXr1ao0aN4sd5\nAOo8LpkAAINs3bpV1dXVioiI0MWLF5WTk6PU1FQlJSU5+lRWVjquH77VSy+9pOTkZC1fvlw9e/bU\nH3/8ofj4eHeWDwD3BIEYAAxRWFiot956S35+fnrttddksVgkSY0aNXLql5GR4fLjOUlq3LixJk2a\npPT0dH333XcKDw9X79693VI7ANxLBGIAqIeOHj2qq1evqqqqSsXFxfr666/18ccfq1GjRsrOzlZg\nYKAkqX///lq0aJGaNWumtm3bas+ePVq7dq38/PxU023qp0yZokWLFunIkSNas2aNu4cFAPcEgRgA\n6pGbu75xcXGSbuz++vn5qUuXLpoxY4ZeffVVRxiWpPXr1yshIUFJSUmqqqpS37599dVXX2nYsGGO\nc92qdevW6tOnj44dO6axY8e6Z1AAcI/xpDoAwF0rLi5W27ZtlZCQUOODOgCgLmKHGABwR7///rtO\nnz6tRYsWyWq1KiEhwdMlAUCt4bZrAIA7Wr16tSIjI3XixAmtW7dOQUFBni4JAGoNl0wAAADAaOwQ\nAwAAwGgEYgAAABiNQAwAAACjEYgBAABgNAIxAAAAjEYgBgAAgNEIxAAAADAagRgAAABGIxADAADA\naP8HZCfV9NqkN/EAAAAASUVORK5CYII=\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0xb09ee64c>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "fig = plt.figure(figsize=(8,4.5), facecolor='white', edgecolor='white')\n",
    "plt.axis([min(daysWithHosts), max(daysWithHosts), 0, max(hosts)+500])\n",
    "plt.grid(b=True, which='major', axis='y')\n",
    "plt.xlabel('Day')\n",
    "plt.ylabel('Hosts')\n",
    "plt.plot(daysWithHosts, hosts)\n",
    "pass"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(3e) Exercise: Average Number of Daily Requests per Hosts**\n",
    "####Next, let's determine the average number of requests on a day-by-day basis. We'd like a list by increasing day of the month and the associated average number of requests per host for that day. Make sure you cache the resulting RDD `avgDailyReqPerHost` so that we can reuse it in the next exercise.\n",
    "####To compute the average number of requests per host, get the total number of request across all hosts and divide that by the number of unique hosts.\n",
    "####*Since the log only covers a single month, you can skip checking for the month.*\n",
    "####*Also to keep it simple, when calculating the approximate average use the integer value - you do not need to upcast to float*"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 41,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Average number of daily requests per Hosts is [(1, 13), (3, 12), (4, 14), (5, 12), (6, 12), (7, 13), (8, 13), (9, 14), (10, 13), (11, 14), (12, 13), (13, 13), (14, 13), (15, 13), (16, 13), (17, 13), (18, 13), (19, 12), (20, 12), (21, 13), (22, 12)]\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "dayAndHostTuple = access_logs.map(lambda log: (log.date_time.date().day, 1)).reduceByKey(lambda a, b : a + b).distinct()\n",
    "\n",
    "groupedByDay = dayAndHostTuple.join(dailyHosts)\n",
    "\n",
    "sortedByDay = groupedByDay.sortByKey()\n",
    "\n",
    "avgDailyReqPerHost = (sortedByDay.map(lambda (a, b) : (a,b[0]/b[1]))).cache()\n",
    "\n",
    "avgDailyReqPerHostList = avgDailyReqPerHost.take(30)\n",
    "print 'Average number of daily requests per Hosts is %s' % avgDailyReqPerHostList"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 42,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Average number of daily requests per hosts (3e)\n",
    "Test.assertEquals(avgDailyReqPerHostList, [(1, 13), (3, 12), (4, 14), (5, 12), (6, 12), (7, 13), (8, 13), (9, 14), (10, 13), (11, 14), (12, 13), (13, 13), (14, 13), (15, 13), (16, 13), (17, 13), (18, 13), (19, 12), (20, 12), (21, 13), (22, 12)], 'incorrect avgDailyReqPerHostList')\n",
    "Test.assertTrue(avgDailyReqPerHost.is_cached, 'incorrect avgDailyReqPerHost.is_cache')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(3f) Exercise: Visualizing the Average Daily Requests per Unique Host**\n",
    "####Using the result `avgDailyReqPerHost` from the previous exercise, use `matplotlib` to plot a \"Line\" graph of the average daily requests per unique host by day.\n",
    "#### `daysWithAvg` should be a list of days and `avgs` should be a list of average daily requests per unique hosts for each corresponding day."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 45,
   "metadata": {
    "collapsed": false
   },
   "outputs": [],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "daysWithAvg = avgDailyReqPerHost.map(lambda (x, y) : x).collect()\n",
    "avgs = avgDailyReqPerHost.map(lambda (x, y): y).collect()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 46,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Average Daily Requests per Unique Host (3f)\n",
    "Test.assertEquals(daysWithAvg, [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22], 'incorrect days')\n",
    "Test.assertEquals(avgs, [13, 12, 14, 12, 12, 13, 13, 14, 13, 14, 13, 13, 13, 13, 13, 13, 13, 12, 12, 13, 12], 'incorrect avgs')"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 47,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "data": {
      "image/png": "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\n8gEAAOBjjgit/fv3165duySZ1bAWL16sxYsXy+VyaceOHapRo4auvPJKrV27VsOHD9cdd9yh4OBg\n3XzzzZo5Rj3mAAAgAElEQVQ8eXJezysAAACKJkeE1h07dhRov5iYGH344Yc+rgYAAABOExAXYgEA\nAKB4I7QCAADA8QitAAAAcDxCKwAAABzvb1+I9d1332ndunXat2+fevfurYiICO3evVsVKlRQmTJl\nCrNGAAAAFHNeh9bTp0/roYce0rx58ySZKao6duyoiIgI9e3bV40aNdL48eMLu04AAAAUY163B0yY\nMEEpKSmaPHmyvv32W529oFbHjh21YsWKQi0QAAAA8Hqkdd68eXriiSf02GOP6dSpUx731apVSz/9\n9FOhFQcAAABIf2Okdffu3bruuuvOed9FF12UtxQrAAAAUFi8Dq3h4eHnHU394YcfdNlll11wUQAA\nAMDZvA6tsbGxmjhxon7++We5XK687QcPHtTUqVPVuXPnQi0QAAAA8Dq0JiYm6tSpU6pfv766desm\nSXr88cfVoEEDHT16VKNHjy70IgEAAFC8eR1aL730Un3++efq2bOnNm/erBIlSujrr79WbGysPv30\nU4WFhfmiTgAAABRjf2txgUsvvVQvv/xyYdcCAAAAnBPLuAIAAMDxvB5pjYuL87gA62xBQUEqX768\nmjRpoq5du6pUqVIXXCAAAADgdWhds2aNDh06pEOHDik4OFhhYWHKysrS6dOnVa5cOUnSc889p7p1\n62rdunWqUqVKoRcNAACA4sXr9oC33npLl1xyiVJSUnTkyBFlZmbq6NGjWrBggS655BKtWLFCGzZs\n0IEDBzRy5Ehf1AwAAIBixuuR1scee0yDBw9Wjx49fn+S4GDddddd+vXXXzVo0CBt3LhRI0aM0LPP\nPluoxQIAAKB48nqkdfPmzapfv/4576tfv76+/PJLSdI111yjrKysC6sOAAAA0N8IrWXLltWaNWvO\ned+aNWt0ySWXSJKOHj2qsmXLXlh1AAAAgP5Ge8A999yjpKQk5ebmqnv37qpSpYr+97//adGiRZoy\nZYoGDhwoSUpLS1NUVFShFwwAAIDix+vQOnHiRGVmZmrSpEmaNGmSx309e/bUxIkTJUktWrRQhw4d\nCqdKAAAAFGteh9bSpUtrwYIFeuKJJ7Ru3Trt27dPYWFhuvHGGz1GVtu1a1eohQIAAKD4+lvLuEpS\n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\nf91rsd4csgeIAAAAAElFTkSuQmCC\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0xb071528c>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "fig = plt.figure(figsize=(8,4.2), facecolor='white', edgecolor='white')\n",
    "plt.axis([0, max(daysWithAvg), 0, max(avgs)+2])\n",
    "plt.grid(b=True, which='major', axis='y')\n",
    "plt.xlabel('Day')\n",
    "plt.ylabel('Average')\n",
    "plt.plot(daysWithAvg, avgs)\n",
    "pass"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "### **Part 4: Exploring 404 Response Codes**\n",
    " \n",
    "####Let's drill down and explore the error 404 response code records. 404 errors are returned when an endpoint is not found by the server (i.e., a missing page or object)."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4a) Exercise: Counting 404 Response Codes**\n",
    "#### Create a RDD containing only log records with a 404 response code. Make sure you `cache()` the RDD `badRecords` as we will use it in the rest of this exercise.\n",
    " \n",
    "#### How many 404 records are in the log?"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 50,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Found 6185 404 URLs\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "badRecords = (access_logs.filter(lambda log: log.response_code == 404)).cache()\n",
    "              \n",
    "print 'Found %d 404 URLs' % badRecords.count()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 51,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Counting 404 (4a)\n",
    "Test.assertEquals(badRecords.count(), 6185, 'incorrect badRecords.count()')\n",
    "Test.assertTrue(badRecords.is_cached, 'incorrect badRecords.is_cached')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4b) Exercise: Listing 404 Response Code Records**\n",
    "####Using the RDD containing only log records with a 404 response code that you cached in part (4a), print out a list up to 40 **distinct** endpoints that generate 404 errors -  *no endpoint should appear more than once in your list.*"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 56,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "404 URLS: [u'/11/history/apollo/images/', u'/128.159.104.89/tv/tv.html', u'/imag', u'/shuttle/missionssts-70/woodpecker.html', u'/~terrig/bookmark.html', u'/elv/ATLAS_CENTAUR/p-ae.gif', u'/pub.win', u'/ksc.nasa.gov/images/ksclogo-medium.gif', u'/history/apollo-13', u'/shuttle/missioins/sts-70/movies/', u'/shuttle/missions/sts-69/mission-sts-74.html', u'/shuttle/missions/sts-80/mission-sts-80.html', u'/histort/apollo/apollo13', u'/www/ksc', u'/shuttle/miccions/sts-73/mission-sts-73.html', u'/images/lf.gif', u'/shuttle/Missions/missions.html', u'/ksc', u'/shuttle/missions/mission.html/', u'/images/jpeg/', u'/shuttle/missions/sts-71/sts-69-info.html', u'/images/crawlerway-logo.gif', u'/home/whats-cool.html', u'/procurement/business/ciao1.htm', u'/icons/blank', u'/HISTORY/APOLLO/', u'/finance/main.html', u'/history/apollo/apollo-13/apollo_13.html', u'/shuttle/countdown/images/yforw.gif', u'/intersex.com/crawler.gif', u'/history/apollo-13-info.html', u'/images/hq.jpeg', u'/history/apollo/apollo-13/*.gpg', u'/history/apollo/apollo-13/apollo-11.html', u'/history/discovery', u'/history/apollo/apollo-13/movie', u'/sofware/', u'/sjr/www/', u'/KSC.html', u'/~adverts/graphics/indxlogo.gif']\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "badEndpoints = badRecords.map(lambda log: log.endpoint)\n",
    "\n",
    "badUniqueEndpoints = badEndpoints.distinct()\n",
    "\n",
    "badUniqueEndpointsPick40 = badUniqueEndpoints.take(40)\n",
    "print '404 URLS: %s' % badUniqueEndpointsPick40"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 57,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Listing 404 records (4b)\n",
    "\n",
    "badUniqueEndpointsSet40 = set(badUniqueEndpointsPick40)\n",
    "Test.assertEquals(len(badUniqueEndpointsSet40), 40, 'badUniqueEndpointsPick40 not distinct')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4c) Exercise: Listing the Top Twenty 404 Response Code Endpoints**\n",
    "####Using the RDD containing only log records with a 404 response code that you cached in part (4a), print out a list of the top twenty endpoints that generate the most 404 errors.\n",
    "####*Remember, top endpoints should be in sorted order*"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 58,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Top Twenty 404 URLs: [(u'/pub/winvn/readme.txt', 633), (u'/pub/winvn/release.txt', 494), (u'/shuttle/missions/STS-69/mission-STS-69.html', 431), (u'/images/nasa-logo.gif', 319), (u'/elv/DELTA/uncons.htm', 178), (u'/shuttle/missions/sts-68/ksc-upclose.gif', 156), (u'/history/apollo/sa-1/sa-1-patch-small.gif', 146), (u'/images/crawlerway-logo.gif', 120), (u'/://spacelink.msfc.nasa.gov', 117), (u'/history/apollo/pad-abort-test-1/pad-abort-test-1-patch-small.gif', 100), (u'/history/apollo/a-001/a-001-patch-small.gif', 97), (u'/images/Nasa-logo.gif', 85), (u'/shuttle/resources/orbiters/atlantis.gif', 64), (u'/history/apollo/images/little-joe.jpg', 62), (u'/images/lf-logo.gif', 59), (u'/shuttle/resources/orbiters/discovery.gif', 56), (u'/shuttle/resources/orbiters/challenger.gif', 54), (u'/robots.txt', 53), (u'/elv/new01.gif>', 43), (u'/history/apollo/pad-abort-test-2/pad-abort-test-2-patch-small.gif', 38)]\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "badEndpointsCountPairTuple = badRecords.map(lambda log: (log.endpoint, 1))\n",
    "\n",
    "badEndpointsSum = badEndpointsCountPairTuple.reduceByKey(lambda a, b : a + b)\n",
    "\n",
    "badEndpointsTop20 = badEndpointsSum.takeOrdered(20, lambda s: -1 * s[1])\n",
    "print 'Top Twenty 404 URLs: %s' % badEndpointsTop20"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 59,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Top twenty 404 URLs (4c)\n",
    "Test.assertEquals(badEndpointsTop20, [(u'/pub/winvn/readme.txt', 633), (u'/pub/winvn/release.txt', 494), (u'/shuttle/missions/STS-69/mission-STS-69.html', 431), (u'/images/nasa-logo.gif', 319), (u'/elv/DELTA/uncons.htm', 178), (u'/shuttle/missions/sts-68/ksc-upclose.gif', 156), (u'/history/apollo/sa-1/sa-1-patch-small.gif', 146), (u'/images/crawlerway-logo.gif', 120), (u'/://spacelink.msfc.nasa.gov', 117), (u'/history/apollo/pad-abort-test-1/pad-abort-test-1-patch-small.gif', 100), (u'/history/apollo/a-001/a-001-patch-small.gif', 97), (u'/images/Nasa-logo.gif', 85), (u'/shuttle/resources/orbiters/atlantis.gif', 64), (u'/history/apollo/images/little-joe.jpg', 62), (u'/images/lf-logo.gif', 59), (u'/shuttle/resources/orbiters/discovery.gif', 56), (u'/shuttle/resources/orbiters/challenger.gif', 54), (u'/robots.txt', 53), (u'/elv/new01.gif>', 43), (u'/history/apollo/pad-abort-test-2/pad-abort-test-2-patch-small.gif', 38)], 'incorrect badEndpointsTop20')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4d) Exercise: Listing the Top Twenty-five 404 Response Code Hosts**\n",
    "####Instead of looking at the endpoints that generated 404 errors, let's look at the hosts that encountered 404 errors. Using the RDD containing only log records with a 404 response code that you cached in part (4a), print out a list of the top twenty-five hosts that generate the most 404 errors."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 60,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Top 25 hosts that generated errors: [(u'piweba3y.prodigy.com', 39), (u'maz3.maz.net', 39), (u'gate.barr.com', 38), (u'm38-370-9.mit.edu', 37), (u'ts8-1.westwood.ts.ucla.edu', 37), (u'nexus.mlckew.edu.au', 37), (u'204.62.245.32', 33), (u'spica.sci.isas.ac.jp', 27), (u'163.206.104.34', 27), (u'www-d4.proxy.aol.com', 26), (u'203.13.168.24', 25), (u'www-c4.proxy.aol.com', 25), (u'203.13.168.17', 25), (u'internet-gw.watson.ibm.com', 24), (u'crl5.crl.com', 23), (u'scooter.pa-x.dec.com', 23), (u'piweba5y.prodigy.com', 23), (u'onramp2-9.onr.com', 22), (u'slip145-189.ut.nl.ibm.net', 22), (u'198.40.25.102.sap2.artic.edu', 21), (u'gn2.getnet.com', 20), (u'msp1-16.nas.mr.net', 20), (u'dial055.mbnet.mb.ca', 19), (u'isou24.vilspa.esa.es', 19), (u'tigger.nashscene.com', 19)]\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "errHostsCountPairTuple = badRecords.map(lambda log: (log.host, 1))\n",
    "\n",
    "errHostsSum = errHostsCountPairTuple.reduceByKey(lambda a, b : a + b)\n",
    "\n",
    "errHostsTop25 = errHostsSum.takeOrdered(25, lambda s: -1 * s[1])\n",
    "print 'Top 25 hosts that generated errors: %s' % errHostsTop25"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 61,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Top twenty-five 404 response code hosts (4d)\n",
    "\n",
    "Test.assertEquals(len(errHostsTop25), 25, 'length of errHostsTop25 is not 25')\n",
    "Test.assertEquals(len(set(errHostsTop25) - set([(u'maz3.maz.net', 39), (u'piweba3y.prodigy.com', 39), (u'gate.barr.com', 38), (u'm38-370-9.mit.edu', 37), (u'ts8-1.westwood.ts.ucla.edu', 37), (u'nexus.mlckew.edu.au', 37), (u'204.62.245.32', 33), (u'163.206.104.34', 27), (u'spica.sci.isas.ac.jp', 27), (u'www-d4.proxy.aol.com', 26), (u'www-c4.proxy.aol.com', 25), (u'203.13.168.24', 25), (u'203.13.168.17', 25), (u'internet-gw.watson.ibm.com', 24), (u'scooter.pa-x.dec.com', 23), (u'crl5.crl.com', 23), (u'piweba5y.prodigy.com', 23), (u'onramp2-9.onr.com', 22), (u'slip145-189.ut.nl.ibm.net', 22), (u'198.40.25.102.sap2.artic.edu', 21), (u'gn2.getnet.com', 20), (u'msp1-16.nas.mr.net', 20), (u'isou24.vilspa.esa.es', 19), (u'dial055.mbnet.mb.ca', 19), (u'tigger.nashscene.com', 19)])), 0, 'incorrect errHostsTop25')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4e) Exercise: Listing 404 Response Codes per Day**\n",
    "####Let's explore the 404 records temporally. Break down the 404 requests by day (`cache()` the RDD `errDateSorted`) and get the daily counts sorted by day as a list.\n",
    "####*Since the log only covers a single month, you can ignore the month in your checks.*"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 66,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "404 Errors by day: [(1, 243), (3, 303), (4, 346), (5, 234), (6, 372), (7, 532), (8, 381), (9, 279), (10, 314), (11, 263), (12, 195), (13, 216), (14, 287), (15, 326), (16, 258), (17, 269), (18, 255), (19, 207), (20, 312), (21, 305), (22, 288)]\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "errDateCountPairTuple = badRecords.map(lambda log: (log.date_time.day, 1))\n",
    "\n",
    "errDateSum = errDateCountPairTuple.reduceByKey(lambda a, b : a + b)\n",
    "\n",
    "errDateSorted = errDateSum.sortByKey().cache()\n",
    "\n",
    "errByDate = errDateSorted.collect()\n",
    "print '404 Errors by day: %s' % errByDate"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 67,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST 404 response codes per day (4e)\n",
    "Test.assertEquals(errByDate, [(1, 243), (3, 303), (4, 346), (5, 234), (6, 372), (7, 532), (8, 381), (9, 279), (10, 314), (11, 263), (12, 195), (13, 216), (14, 287), (15, 326), (16, 258), (17, 269), (18, 255), (19, 207), (20, 312), (21, 305), (22, 288)], 'incorrect errByDate')\n",
    "Test.assertTrue(errDateSorted.is_cached, 'incorrect errDateSorted.is_cached')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4f) Exercise: Visualizing the 404 Response Codes by Day**\n",
    "####Using the results from the previous exercise, use `matplotlib` to plot a \"Line\" or \"Bar\" graph of the 404 response codes by day."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 68,
   "metadata": {
    "collapsed": false
   },
   "outputs": [],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "daysWithErrors404 = errDateSorted.map(lambda (x, y): x).collect()\n",
    "errors404ByDay = errDateSorted.map(lambda (x, y) : y).collect()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 69,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Visualizing the 404 Response Codes by Day (4f)\n",
    "Test.assertEquals(daysWithErrors404, [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22], 'incorrect daysWithErrors404')\n",
    "Test.assertEquals(errors404ByDay, [243, 303, 346, 234, 372, 532, 381, 279, 314, 263, 195, 216, 287, 326, 258, 269, 255, 207, 312, 305, 288], 'incorrect errors404ByDay')"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 70,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "data": {
      "image/png": "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\nMpQ6d06pTZuUCg+Xi6cOHZSqXPm/5BdQqmpVpTp1UmrECKUiIpTavFmp8+fN/9ozeZL7559/qn79\n+qmKFSs8fcKqAAAgAElEQVQqJycnVblyZfXaa6+p48ePF2R3ufLx8VE1a9ZUSimVnp6uXF1d1dCh\nQ3Ns16VLF1W7du2sf3/99ddKp9OpvQ8NnVy8eFHpdDoVFhaW6/GY5JrGggUycvHmm/JGbwmmT1fK\n1VWpGze0i6FePaVee02749uLs2cl2QwPN8/x/vlHqRdflA+E0aMff1GXlKSUu7tS3t4yykK2584d\npXr3lgv9iAjj7z8uTl5vCxcaf99kXT74QJLch25uF8rNm0r98otSy5crNW6cvJbr1VPKyem/5Ldk\nSXkPW7rUPCO+Jk1yjxw5osqUKaNcXFxU9+7d1cCBA1W3bt2Us7OzcnNzU0eOHClQ0BkZGSo9PV1d\nvnxZRUREKEdHRzV//nyllFJJSUlKp9Opzz77LMf3jRo1Sjk4OKi0f4fExowZo3Q6nbpz506ObcuV\nK6f69euX6/GZ5BrX/ftKzZghfwDDhxtv5MIYLlyQxMcUHzj5ceSI/FzWrdPm+Pamb1+lnn7a9K/B\npCSl6tZVqkQJpSIj8/99O3bIB1O/fhyNszWXLyvl5SUlBT/8YLrjDBwoicbZs6Y7Blm29HQpUzDX\nXcp795Q6elSp779XauZMpTp2lAGt4sUlhu3bTfd+ZtIkt1evXuqpp55S586dy/b4uXPn1NNPP616\n9epl6C6VUkoNHjxY6XQ6pdPplKOjo5o7d27Wc7t27VI6nU599913Ob4vLCxM6XQ6denSJaWUUkFB\nQcrFxSXXY9SuXVt17do11+eY5BrPyZNyVQfIlZ8lfnD36qVUo0baxDZ9urwR5HIdRibw88/yWvzx\nR9MdIzJSkgxPT7mIMdR330mM48cbPzbSxp9/ysVV+fJK7dtn2mNdvy63lrt3t8z3WzK9yEh5D9Ey\nhTlzRqkpU6QMC1CqVi2lwsKU+usv4x7HkHzN4BZi27Ztw/vvv4+qD62/WrVqVUyePBlbt24t0AS4\n8ePH49dff8WGDRsQFBSE//3vf5jJRbqtilLA558DDRvKjPYtW4Dp07XtYpCXQYOkj+C+feY/dmSk\ntHR5eNlOMg0vL+ktaop2Ynq9LLUaECALUPzyi8xQNtRLLwEffSR/L+yha/1+/lled0WKSIuwZ54x\n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\nS0REREQ2h0kuEREREdkcJrlEREREZHOY5BIRERGRzWGSS0REREQ2h0kuEREREdkcJrlEREREZHOY\n5BIRERGRzWGSS0REREQ2h0kuEREREdkcJrlEREREZHOY5BIRERGRzWGSS0REREQ2h0kuEREREdkc\nJrlEREREZHOY5BIRERGRzWGSS0REREQ2h0kuEREREdkcJrlEREREZHOY5BIRERGRzWGSS0REREQ2\nh0kuEREREdkci0hyU1JS8N5776Fz584oV64cHBwcEBoamuu2CQkJ6NixI0qWLAk3NzcEBATg1KlT\nuW4bHh4OT09PuLi4oGbNmpgyZQr0er0pT4WIiIiILIBFJLnJyclYtGgR0tPT0atXLwCATqfLsV1S\nUhK8vb2h1+uxevVqLF26FMeOHUPr1q2RnJycbdvp06cjJCQEffr0QVxcHIYNG4awsDAEBweb5ZyI\niIiISDuOWgcAANWrV8f169cBAFevXsXixYtz3W7SpElwdXVFdHQ0SpQoAQBo3rw5atWqhVmzZmHG\njBlZ+5g2bRoGDRqEadOmAQDatGmD9PR0TJgwASEhIahbt64ZzoyIiIiItGARI7kPUkrl+rher0d0\ndDQCAgKyElwAqFatGtq1a4e1a9dmPRYTE4O0tDQEBgZm20dgYCCUUli3bp1pgiciIiIii2BxSW5e\nTpw4gdTUVDRq1CjHcw0bNsTx48dx7949AMChQ4eyHn9QxYoVUbZsWSQmJpo+YCIiIiLSjNUkuVev\nXgUAuLu753jO3d0dSqlsJQ/Ozs5wdXXNsa2bm1vWvoiIiIjINllNkktERERElF9Wk+R6eHgAAK5d\nu5bjuWvXrkGn08HNzS1r27S0NKSmpua6bea+ctO9e3f4+/tn+2rVqlWOOt64uDj4+/vn+P7g4GAs\nWbIk22MJCQnw9/fP0QFi8uTJmDlzZrbHzp49C39/fyQlJWV7PDw8HO+++262x+7cuQN/f3/s3Lkz\n2+MrV67MUY8MAH379uV58Dx4HjwPngfPg+fB87CK81i5cmVWLlajRg00adIEISEhOfaTF53Ka6aX\nRpKTk1G+fHm8//77mPT/7d1/TFX148fx171eMSQGQpJX0iTNxIQBjtRpiSmO/FEK2hLdjKY2dQTN\nEpxp3rXMImsuMU0z5qZombSp6VCG2ioMZCtkusgUKk0UUIGRSpzPH847+eLno3zLey6H52O7m77P\n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\nDvXp00epqamqq6szOxa8wOXLl1VaWuq+bI515gZL3if3btXU1GjAgAFtxoOCgtzHgVsFBgYqPT1d\ncXFxCg4OVkVFhbKyshQXF6e9e/dq/PjxZkeEl7u5rtxcZ24VFBQkwzBUV1enBx980NPR4MWioqIU\nHR3tfmLnoUOH9OGHH6qgoEDFxcXy8/MzOSHMtHDhQjU1NWnp0qWSWGdu6tQlF2ivqKgoRUVFuX8/\ncuRITZ06VREREcrIyKDkArgn0tPTW/1+7Nixio6O1rRp07Rp0yalpaWZlAxmW7ZsmbZt26a1a9cq\nOjra7DhepVNfrhAcHHzb3dra2lr3ceBOAgICNHHiRP3444+6evWq2XHg5W6uKzfXmVvV1tbKZrOp\nR48eno6FDmjq1Kny8/Pj+yOdmMvl0ttvv62VK1dqwYIF7nHWmRs6dcmNjIzUiRMn1NLS0mq8rKxM\nktz/LQTcLR4ZjTvp37+/fH199dNPP7U5VlZWpkcffVQ+Pj4mJENHYxhGm7+/0Hm4XC73KzMzs9Ux\n1pkbOnXJnTp1qhoaGrRz585W4zk5OQoNDdWwYcNMSoaOpK6uTrt371Z0dHSnWDTwzzgcDk2ePFm7\ndu1SQ0ODe7yqqkqFhYVKTEw0MR06kp07d6qpqUkjRowwOwo87K233pLL5dKyZcu0bNmyNsdZZ27o\n1NfkJiQkKD4+XvPnz9eVK1fUv39/5ebmKj8/X1u3bmVXDm3MnDlTYWFhiomJUVBQkCoqKrR69Wpd\nuHBBW7ZsMTsevMC+ffvU2Nio+vp6STfu0nLzH9ITJ06Ur6+vXC6XYmNjNWnSJGVmZqqpqUnLly9X\nSEiIFi1aZGZ8mOBOc6a6ulqzZs1ScnKyHnnkERmGocOHD2vNmjUaMmSI5syZY2Z8eNjq1av15ptv\nKiEhQRMmTFBRUVGr48OHD5ck1hmpcz8MwjBu3EA5LS3NcDqdRrdu3YyoqChjx44dZseCl1q1apUR\nHR1tBAYGGg6HwwgJCTGSkpKMkpISs6PBS/Tr18+w2WyGzWYz7HZ7q19XVla6zzt27Jgxbtw4w8/P\nzwgICDASExONX3/91cTkMMud5kxdXZ2RmJhohIWFGd27dze6detmPPbYY0ZmZqZx5coVs+PDw+Li\n4lrNk1tfdru91bmdfZ2xGQZ3lwYAAIC1dOprcgEAAGBNlFwAAABYDiUXAAAAlkPJBQAAgOVQcgEA\nAGA5lFwAAABYDiUXAAAAlkPJBQAAgOVQcgEAAGA5lFwA8HI5OTmy2+3ul6+vr5xOp55++mmtWrVK\nFy5cMDsiAHgdSi4AdBA5OTkqKirSwYMHtW7dOkVFRendd99VeHi4CgoKzI4HAF7FZhiGYXYIAMB/\nl5OTo5deekklJSWKiYlpdey3337TqFGjdOnSJVVUVCgkJMSklADgXdjJBYAOrE+fPlq9erXq6+u1\nYcMGSVJJSYleeOEFhYWFqXv37goLC1NycrKqqqrcP3fmzBk5HA6tWrWqzXseOXJEdrtdO3fu9Njn\nAIB/GyUXADq4Z555Rl26dNGRI0ckSZWVlRo4cKA++OAD5efn67333tO5c+cUGxurmpoaSVK/fv30\n7LPPav369WppaWn1fmvXrlVoaKgSExM9/lkA4N/iMDsAAOCf8fPzU3BwsM6dOydJSkpKUlJSkvt4\nS0uLJkyYoF69emnbtm1KTU2VJKWlpWnMmDHavXu3nnvuOUnS2bNn9dVXX2n58uWy29kHAdBxsYIB\ngAXc+vWKhoYGZWRkaMCAAeratascDof8/f3V2NiokydPus8bPXq0IiMjlZ2d7R5bv3697Ha75s2b\n59H8APBvo+QCQAfX2Niompoa9e7dW5KUnJys7OxszZs3T/n5+SouLlZxcbF69uyppqamVj/7yiuv\nqKCgQBUVFbp+/bo2btyoadOm8QU2AB0elysAQAe3d+9etbS0KC4uTpcvX9aePXvkcrm0ePFi9zlX\nr151X497q5kzZyojI0Nr167VsGHDdP78eS1cuNCT8QHgnqDkAkAHVlVVpddee02BgYF6+eWXZbPZ\nJEk+Pj6tztu0aVObL5hJUrdu3TRv3jxlZ2fru+++U0xMjEaMGOGR7ABwL1FyAaCDKCsr07Vr19Tc\n3Kzq6mp98803+uyzz+Tj46O8vDwFBwdLkp566illZWXpgQce0MMPP6zDhw9r8+bNCgwM1O1ujb5g\nwQJlZWXp2LFj+vTTTz39sQDgnqDkAoCXu7k7m5KSIunGLm1gYKAGDx6sJUuWaM6cOe6CK0nbtm1T\nWlqaFi9erObmZo0aNUoHDhzQxIkT3e91q9DQUI0cOVLHjx9XcnKyZz4UANxjPPEMADq56upqPfzw\nw0pLS7vtwyEAoCNiJxcAOqk//vhDp06dUlZWlhwOh9LS0syOBAD/Gm4hBgCd1MaNGzVmzBidOHFC\nW7duldPpNDsSAPxruFwBAAAAlsNOLgAAACyHkgsAAADLoeQCAADAcii5AAAAsBxKLgAAACyHkgsA\nAADLoeQCAADAcii5AAAAsJz/AHPUJTMhR6wTAAAAAElFTkSuQmCC\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0xb0a58eac>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "fig = plt.figure(figsize=(8,4.2), facecolor='white', edgecolor='white')\n",
    "plt.axis([0, max(daysWithErrors404), 0, max(errors404ByDay)])\n",
    "plt.grid(b=True, which='major', axis='y')\n",
    "plt.xlabel('Day')\n",
    "plt.ylabel('404 Errors')\n",
    "plt.plot(daysWithErrors404, errors404ByDay)\n",
    "pass"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4g) Exercise: Top Five Days for 404 Response Codes **\n",
    "####Using the RDD `errDateSorted` you cached in the part (4e), what are the top five days for 404 response codes and the corresponding counts of 404 response codes?"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 71,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Top Five dates for 404 requests: [(7, 532), (8, 381), (6, 372), (4, 346), (15, 326)]\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "topErrDate = errDateSorted.takeOrdered(5, lambda s: -1 * s[1])\n",
    "print 'Top Five dates for 404 requests: %s' % topErrDate"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 72,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Five dates for 404 requests (4g)\n",
    "Test.assertEquals(topErrDate, [(7, 532), (8, 381), (6, 372), (4, 346), (15, 326)], 'incorrect topErrDate')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4h) Exercise: Hourly 404 Response Codes**\n",
    "####Using the RDD `badRecords` you cached in the part (4a) and by hour of the day and in increasing order, create an RDD containing how many requests had a 404 return code for each hour of the day (midnight starts at 0). Cache the resulting RDD hourRecordsSorted and print that as a list."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 73,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Top hours for 404 requests: [(0, 175), (1, 171), (2, 422), (3, 272), (4, 102), (5, 95), (6, 93), (7, 122), (8, 199), (9, 185), (10, 329), (11, 263), (12, 438), (13, 397), (14, 318), (15, 347), (16, 373), (17, 330), (18, 268), (19, 269), (20, 270), (21, 241), (22, 234), (23, 272)]\n"
     ]
    }
   ],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "hourCountPairTuple = badRecords.map(lambda log: (log.date_time.hour, 1))\n",
    "\n",
    "hourRecordsSum = hourCountPairTuple.reduceByKey(lambda a, b : a + b)\n",
    "\n",
    "hourRecordsSorted = (hourRecordsSum.sortByKey()).cache()\n",
    "\n",
    "errHourList = hourRecordsSorted.collect()\n",
    "print 'Top hours for 404 requests: %s' % errHourList"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 74,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Hourly 404 response codes (4h)\n",
    "Test.assertEquals(errHourList, [(0, 175), (1, 171), (2, 422), (3, 272), (4, 102), (5, 95), (6, 93), (7, 122), (8, 199), (9, 185), (10, 329), (11, 263), (12, 438), (13, 397), (14, 318), (15, 347), (16, 373), (17, 330), (18, 268), (19, 269), (20, 270), (21, 241), (22, 234), (23, 272)], 'incorrect errHourList')\n",
    "Test.assertTrue(hourRecordsSorted.is_cached, 'incorrect hourRecordsSorted.is_cached')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "#### **(4i) Exercise: Visualizing the 404 Response Codes by Hour**\n",
    "####Using the results from the previous exercise, use `matplotlib` to plot a \"Line\" or \"Bar\" graph of the 404 response codes by hour."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 75,
   "metadata": {
    "collapsed": false
   },
   "outputs": [],
   "source": [
    "# TODO: Replace <FILL IN> with appropriate code\n",
    "\n",
    "hoursWithErrors404 = hourRecordsSorted.map(lambda (x, y) : x).collect()\n",
    "errors404ByHours = hourRecordsSorted.map(lambda (x, y): y).collect()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 76,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "1 test passed.\n",
      "1 test passed.\n"
     ]
    }
   ],
   "source": [
    "# TEST Visualizing the 404 Response Codes by Hour (4i)\n",
    "Test.assertEquals(hoursWithErrors404, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'incorrect hoursWithErrors404')\n",
    "Test.assertEquals(errors404ByHours, [175, 171, 422, 272, 102, 95, 93, 122, 199, 185, 329, 263, 438, 397, 318, 347, 373, 330, 268, 269, 270, 241, 234, 272], 'incorrect errors404ByHours')"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 77,
   "metadata": {
    "collapsed": false
   },
   "outputs": [
    {
     "data": {
      "image/png": "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\ncgEAAGA5/w80DfbAB9qrAwAAAABJRU5ErkJggg==\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0xb037468c>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "fig = plt.figure(figsize=(8,4.2), facecolor='white', edgecolor='white')\n",
    "plt.axis([0, max(hoursWithErrors404), 0, max(errors404ByHours)])\n",
    "plt.grid(b=True, which='major', axis='y')\n",
    "plt.xlabel('Hour')\n",
    "plt.ylabel('404 Errors')\n",
    "plt.plot(hoursWithErrors404, errors404ByHours)\n",
    "pass"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 2",
   "language": "python",
   "name": "python2"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 2
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython2",
   "version": "2.7.6"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 0
}
