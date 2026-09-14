import tempfile
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch

import auth_store as store
from backend.auth import require_upload, require_model_switch, require_admin
from fastapi import HTTPException
from fastapi.testclient import TestClient


class UserPermissionsTest(unittest.TestCase):
    def test_http_permissions(self):
        # Replace RAG only: exercise real routes, cookies, users and database.
        services_module = types.ModuleType('backend.services')
        from unittest.mock import MagicMock
        services_module.AppServices = MagicMock()
        services_module.AppServices.return_value.switch_model_mode.return_value = {'mode': 'dashscope'}
        with tempfile.TemporaryDirectory() as directory, patch.object(store.config, 'auth_db_path', str(Path(directory) / 'auth.db')), patch.object(store, 'migrate_legacy_history'), patch.dict(sys.modules, {'backend.services': services_module}):
            store.init_db()
            from backend.main import app
            with TestClient(app) as admin, TestClient(app) as member:
                self.assertEqual(member.get('/api/admin/users').status_code, 401)
                response = member.post('/api/auth/register', json={'username': 'http_test', 'password': 'secret123'})
                self.assertEqual(response.status_code, 200)
                user_id = response.json()['data']['id']
                self.assertEqual(member.get('/api/admin/users').status_code, 403)
                permissions = {'can_upload': True, 'can_switch_models': True}
                url = f'/api/admin/users/{user_id}/permissions'
                self.assertEqual(member.patch(url, json=permissions).status_code, 403)
                self.assertEqual(member.post('/api/models/switch', json={'mode': 'dashscope'}).status_code, 403)
                self.assertEqual(member.post('/api/upload').status_code, 403)

                self.assertEqual(member.post('/api/batch-ingest', json={'path': 'test'}).status_code, 403)
                self.assertEqual(admin.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'}).status_code, 200)
                self.assertEqual(admin.get('/api/admin/users').status_code, 200)
                from backend.main import services
                with patch.object(services, 'batch_ingest', return_value={'success_count': 0}) as ingest:
                    files = [('files', ('docs/a.txt', b'hello', 'text/plain'))]
                    self.assertEqual(member.post('/api/batch-upload', files=files).status_code, 403)
                    with tempfile.TemporaryDirectory() as upload_root, patch.object(store.config, 'PROJECT_ROOT', Path(upload_root)):
                        response = admin.post('/api/batch-upload', files=files, data={'dry_run': 'true'})
                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(ingest.call_args.args[2])
                        ingest.reset_mock()
                        self.assertEqual(admin.post('/api/batch-upload', files=[('files', ('../a.txt', b'x'))]).status_code, 400)
                        ingest.assert_not_called()
                new_account = {'username': 'created_by_admin', 'password': 'secret123', 'display_name': 'New user'}
                self.assertEqual(member.post('/api/admin/users', json=new_account).status_code, 403)
                created = admin.post('/api/admin/users', json=new_account)
                self.assertEqual(created.status_code, 201)
                self.assertEqual(created.json()['data']['role'], 'user')
                self.assertNotIn('set-cookie', created.headers)
                self.assertEqual(admin.get('/api/auth/me').json()['data']['username'], 'admin')
                self.assertEqual(admin.post('/api/admin/users', json=new_account).status_code, 409)
                self.assertEqual(admin.post('/api/admin/users', json=dict(new_account, username='x')).status_code, 422)
                with TestClient(app) as new_user:
                    self.assertEqual(new_user.post('/api/auth/login', json=new_account).status_code, 200)
                self.assertEqual(admin.patch(url, json=permissions).status_code, 200)
                self.assertTrue(member.get('/api/auth/me').json()['data']['can_upload'])
                self.assertEqual(member.post('/api/models/switch', json={'mode': 'dashscope'}).status_code, 200)
                # Missing file produces validation failure only after permission passes.
                self.assertEqual(member.post('/api/upload').status_code, 422)
                self.assertEqual(admin.patch(url, json={'can_upload': False, 'can_switch_models': False}).status_code, 200)
                self.assertEqual(member.post('/api/upload').status_code, 403)
                self.assertEqual(admin.patch(url, json=dict(permissions, enabled=False)).status_code, 200)
                self.assertEqual(member.get('/api/auth/me').status_code, 401)
                self.assertEqual(member.post('/api/auth/login', json={'username': 'http_test', 'password': 'secret123'}).status_code, 401)
                self.assertEqual(admin.patch(url, json=dict(permissions, enabled=True)).status_code, 200)
                self.assertEqual(member.get('/api/auth/me').status_code, 401)
                self.assertEqual(member.post('/api/auth/login', json={'username': 'http_test', 'password': 'secret123'}).status_code, 200)

    def test_grants_revocation_and_safe_account_listing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(store.config, 'auth_db_path', str(Path(directory) / 'auth.db')), patch.object(store, 'migrate_legacy_history'):
            store.init_db()
            store.init_db()
            user = store.register_user('permission_test', 'secret123')
            token = store.create_auth_session(user.id)
            with self.assertRaises(HTTPException):
                require_upload(user)
            store.set_user_permissions(user.id, True, False)
            user = store.get_user_by_token(token)
            require_upload(user)
            with self.assertRaises(HTTPException):
                require_model_switch(user)
            with self.assertRaises(HTTPException):
                require_admin(user)
            store.set_user_permissions(user.id, False, True)
            user = store.get_user_by_token(token)
            require_model_switch(user)
            with self.assertRaises(HTTPException):
                require_upload(user)
            users = store.list_users()
            self.assertFalse(any('password' in key for item in users for key in item))
            admin = store.authenticate('admin', 'admin123')
            with self.assertRaises(ValueError):
                store.set_user_permissions(admin.id, False, False)
            with self.assertRaises(FileNotFoundError):
                store.set_user_permissions(999999, True, True)


if __name__ == '__main__':
    unittest.main()
