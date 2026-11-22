from django.test import TestCase

# Create your tests here.


class PwaTests(TestCase):
    def test_manifest_and_service_worker_are_public_at_root(self):
        manifest = self.client.get('/manifest.webmanifest')
        self.assertEqual(manifest['Content-Type'], 'application/manifest+json')
        self.assertEqual(manifest.json()['start_url'], '/')
        worker = self.client.get('/sw.js')
        self.assertEqual(worker['Content-Type'], 'text/javascript')
        self.assertContains(worker, "addEventListener('fetch'")
        self.assertContains(self.client.get('/login/'), 'rel="manifest"')
