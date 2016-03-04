#    Copyright 2011 OpenStack LLC
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from manila import context
from manila import test


class ContextTestCase(test.TestCase):

    def test_request_context_elevated(self):
        user_context = context.RequestContext(
            'fake_user', 'fake_project', is_admin=False)
        self.assertFalse(user_context.is_admin)
        self.assertEqual([], user_context.roles)
        admin_context = user_context.elevated()
        self.assertFalse(user_context.is_admin)
        self.assertTrue(admin_context.is_admin)
        self.assertFalse('admin' in user_context.roles)
        self.assertTrue('admin' in admin_context.roles)

    def test_request_context_sets_is_admin(self):
        ctxt = context.RequestContext('111',
                                      '222',
                                      roles=['admin', 'weasel'])
        self.assertTrue(ctxt.is_admin)

    def test_request_context_sets_is_admin_upcase(self):
        ctxt = context.RequestContext('111',
                                      '222',
                                      roles=['Admin', 'weasel'])
        self.assertTrue(ctxt.is_admin)

    def test_request_context_read_deleted(self):
        ctxt = context.RequestContext('111',
                                      '222',
                                      read_deleted='yes')
        self.assertEqual('yes', ctxt.read_deleted)

        ctxt.read_deleted = 'no'
        self.assertEqual('no', ctxt.read_deleted)

    def test_request_context_read_deleted_invalid(self):
        self.assertRaises(ValueError,
                          context.RequestContext,
                          '111',
                          '222',
                          read_deleted=True)

        ctxt = context.RequestContext('111', '222')
        self.assertRaises(ValueError,
                          setattr,
                          ctxt,
                          'read_deleted',
                          True)

    def test_extra_args_to_context_get_logged(self):
        info = {}

        def fake_warn(log_msg, other_args):
            info['log_msg'] = log_msg % other_args

        self.mock_object(context.LOG, 'warning', fake_warn)

        c = context.RequestContext('user',
                                   'project',
                                   extra_arg1='meow',
                                   extra_arg2='wuff',
                                   user='user',
                                   tenant='project')
        self.assertTrue(c)
        self.assertIn("'extra_arg1': 'meow'", info['log_msg'])
        self.assertIn("'extra_arg2': 'wuff'", info['log_msg'])
        # user and tenant kwargs get popped off before we log anything
        self.assertNotIn("'user': 'user'", info['log_msg'])
        self.assertNotIn("'tenant': 'project'", info['log_msg'])
