import time
from urllib.parse import urlencode
from http.client import responses
import requests


token = ''
app_id = ''


class VKClient:
    __API_BASE_URL = 'https://api.vk.com/method/'

    def __init__(self, token, user_id=None, version='5.124'):
        self.__vksite = 'https://vk.com/'
        self.__token = token
        self.__version = version
        self.__params = {'access_token': self.__token, 'v': self.__version}
        # try to instantiate
        user = self.get_users(user_ids=user_id)
        if not user['success']:
            self.__user_id = None
            self.__first_name = None
            self.__last_name = None
            self.__domain = None
            # error message will be in status
            self.__status = user['object']
        else:
            self.__user_id = str(user['object'][0]['id'])
            self.__first_name = user['object'][0]['first_name']
            self.__last_name = user['object'][0]['last_name']
            self.__domain = user['object'][0]['domain']
            self.__status = 'Initialised'
        # following string for debug only
        print(f'{self.__status}: {self.__first_name} {self.__last_name} ({self.__vksite + self.__domain})')

    def get_id(self):
        return self.__user_id

    def get_fname(self):
        return self.__first_name

    def get_lname(self):
        return self.__last_name

    def get_domain(self):
        return self.__domain

    def get_status(self):
        return self.__status

    def __str__(self):
        if not self.__user_id:
            return self.__status
        return self.__vksite + self.__domain

    def __and__(self, other):
        if type(other).__name__ != type(self).__name__:
            return False
        mutual = self.get_mutual_friends(friends_ids=[other.get_id()], user_id=self.get_id())
        if not mutual['success']:
            return False
        result = []
        for friend in mutual['object']:
            # this string for debug only
            print(f'Let\'s get {len(friend["common_friends"])} mutual friends...')
            for x in friend['common_friends']:
                result.append(VKClient(self.__token, x))
                # to prevent ban from server
                time.sleep(0.5)
        return result

    @staticmethod
    def get_auth_link(app_id: str, scope='status'):
        """
        This method gives link which can be used in browser to get VK authentication token. After moving by
        link in browser, you'll be redirected to another page, and parameter "access_token" will be in URL.
        :param app_id: APP ID received during creation "standalone" app at https://vk.com/apps?act=manage
        :param scope: one or more statuses from https://vk.com/dev/permissions joined in string with comma delimiter
        :return: link for usage in browser
        """
        oauth_api_base_url = 'https://oauth.vk.com/authorize'
        redirect_uri = 'https://oauth.vk.com/blank.html'
        oauth_params = {
            'redirect_uri': redirect_uri,
            'scope': scope,
            'response_type': 'token',
            'client_id': app_id
        }
        return '?'.join([oauth_api_base_url, urlencode(oauth_params)])

    @staticmethod
    def prepare_params(params):
        """
        This static method normalize all parameters that can be passed as integer or mixed list of integers and strings,
        and makes from them one string that can be accepted as request parameter
        :param params: integer, string or list of integers and string
        :return: string with values separated by commas
        """
        result = ''
        if type(params) is int:
            result = str(params)
        elif type(params) is str:
            result = params
        elif type(params) is list:
            result = ','.join([str(x) for x in params])
        return result

    @staticmethod
    def get_response_content(response: requests.Response, path='response', sep=','):
        """
        This method returns object from JSON response using specified path OR returns errors
        We can hide errors and make one logic for processing any responses
        :param response: response object
        :param path: path to JSON object, separated by comma
        :param sep: delimiter sign in path string
        :return: JSON object, None if object not found or Error string in case network/protocols/API errors
        """
        # result['object'] might contain requested object from JSON or error string
        # result['success'] has True if requested path found (if specified) and no error codes
        result = {'object': None, 'success': False}
        if not (200 <= response.status_code < 300):
            result['object'] = f'Request error: {str(response.status_code)} ({responses[response.status_code]})'
            return result
        # Do not try to parse JSON if we don't need response body, so checking performed only by status code
        if not path or path == '':
            result['object'] = response
            result['success'] = True
            return result
        try:
            result['object'] = response.json()
        except ValueError:
            result['object'] = 'JSON decode error'
            return result
        if result['object'].get('error'):
            # try to get error message if present, otherwise return null API error description
            result['object'] = 'API error: ' + result['object'].get('error', {'error_msg': None})['error_msg']
            return result
        # Let's extract nested object using string path
        for key in path.split(sep):
            # correcting some small mistypes in path (spaces, multiple delimiters)
            if key == '':
                continue
            # If we found list in JSON we can no longer go forward, so we stop and return what we have
            if type(result['object']) is list:
                result['success'] = True
                return result
            else:
                found = result['object'].get(key.strip())
            # if any part of path doesn't found, we return null object
            if found is None:
                result['object'] = None
                return result
            result['object'] = found
        result['success'] = True
        return result

    def get_user_status(self, user_id=None):
        """
        This method gets user status
        :user_id: ID of user, if None - your token's account ID will be taken
        :return: by key 'object' - status text or error string,
                 by key 'success' - True if request was successful
        """
        params = {}
        if user_id:
            params = {'user_id': self.prepare_params(user_id)}
        response = requests.get(self.__API_BASE_URL + 'status.get', params={**self.__params, **params})
        return self.get_response_content(response, path='response,text')

    def get_users(self, fields=['domain'], user_ids=None):
        """
        This method receive users info by their ID's
        Description here: https://vk.com/dev/users.get
        :param user_ids: list of one or more user IDs in strings form
        :return: by key 'object' - list of requested user IDs with requested fields or error string,
                 by key 'success' - True if request was successful
        """
        params = {}
        if fields:
            params.update({'fields': fields})
        if user_ids:
            params.update({'user_ids': self.prepare_params(user_ids)})
        response = requests.get(self.__API_BASE_URL + 'users.get', params={**self.__params, **params})
        return self.get_response_content(response)

    def get_mutual_friends(self, friends_ids=None, user_id=None):
        """
        This method returns target users and their common friends with specified user
        Description here: https://vk.com/dev/friends.getMutual
        :param user_id: user ID with whom we'll compare other users, if None - your token's account ID will be taken
        :param friends_ids: list of one or more friends user IDs in strings form
        :return: by key 'object' - list of requested user IDs with list of common friends or error,
                 by key 'success' - True if request was successful
        """
        params = {}
        if friends_ids:
            params.update({'target_uids': self.prepare_params(friends_ids)})
        if user_id:
            params.update({'source_uid': user_id})
        response = requests.get(self.__API_BASE_URL + 'friends.getMutual', params={**self.__params, **params})
        return self.get_response_content(response, path='response')


def process_single_user(target_uids: list, uid=None):
    print('\nCreating user...')
    client = VKClient(token, uid)
    if not client.get_id():
        print(f'Error: {client.get_status()}')
        return
    print(f'Found user #{client.get_id()}: {client.get_fname()} {client.get_lname()} ({client})')
    print('\nChecking status...')
    status = client.get_user_status(uid)
    if not status['success']:
        print(f'Can\'t get status. {status["object"]}')
        return
    print(f'User status: {status["object"]}')
    print('\nChecking mutual friends...')
    mutual = client.get_mutual_friends(friends_ids=target_uids, user_id=uid)
    if not mutual['success']:
        print(f'Can\'t get mutual friends. {mutual["object"]}')
        return
    print(f'Mutual friends:')
    for person in mutual['object']:
        print(f'User #{str(person["id"])} has {str(person["common_count"])} mutual friends')


user_id = '22'
target_user_ids = ['6492', '3422', '2745']
while app_id == '':
    app_id = input('Please input your APP ID: ')
if token == '':
    print('Token was not set. Please use below link to get VK token.')
    print(VKClient.get_auth_link(app_id, 'status,friends'))
while token == '':
    token = input('Please input received token: ')
process_single_user(target_uids=target_user_ids, uid=user_id)

print('\nLet\'s get list of mutual friends and print their domains...')
client1 = VKClient(token, 2745)
client2 = VKClient(token, 22)
print('\nMutual friends of those persons are:')
print(*(client1 & client2), sep='\n')
