from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, date, time, timedelta
from rest_framework.test import APIClient
from rest_framework import status
from .models import Broadcast, Event, Group, Media


class BroadcastModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )

    def test_broadcast_creation(self):
        """Test broadcast model creation"""
        broadcast = Broadcast.objects.create(
            title='Test Broadcast',
            description='This is a test broadcast',
            priority='important',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(hours=24),
            audience_type='all',
            created_by=self.user
        )
        
        self.assertEqual(broadcast.title, 'Test Broadcast')
        self.assertEqual(broadcast.priority, 'important')
        self.assertEqual(broadcast.audience_type, 'all')
        self.assertEqual(broadcast.created_by, self.user)

    def test_broadcast_visibility(self):
        """Test broadcast visibility logic"""
        now = timezone.now()
        
        # Create visible broadcast
        visible_broadcast = Broadcast.objects.create(
            title='Visible Broadcast',
            description='This is visible',
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            is_published=True,
            created_by=self.user
        )
        
        # Create invisible broadcast (future)
        future_broadcast = Broadcast.objects.create(
            title='Future Broadcast',
            description='This is in the future',
            start_date=now + timedelta(hours=1),
            end_date=now + timedelta(hours=2),
            is_published=True,
            created_by=self.user
        )
        
        self.assertTrue(visible_broadcast.is_visible)
        self.assertFalse(future_broadcast.is_visible)

    def test_acknowledgment_rate(self):
        """Test acknowledgment rate calculation"""
        broadcast = Broadcast.objects.create(
            title='Test Broadcast',
            description='Test',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(hours=24),
            audience_type='all',
            created_by=self.user
        )
        
        # Create additional users
        user2 = User.objects.create_user(username='user2', email='user2@example.com')
        user3 = User.objects.create_user(username='user3', email='user3@example.com')
        
        # Acknowledge by 2 out of 3 users
        broadcast.acknowledged_by.add(self.user, user2)
        
        # Should be 66.67% (2/3 * 100)
        self.assertAlmostEqual(broadcast.acknowledgment_rate, 66.67, places=1)


class EventModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_event_creation(self):
        """Test event model creation"""
        event = Event.objects.create(
            title='Test Event',
            description='This is a test event',
            date=date.today() + timedelta(days=7),
            time=time(14, 30),
            venue='Conference Room',
            event_type='internal',
            created_by=self.user
        )
        
        self.assertEqual(event.title, 'Test Event')
        self.assertEqual(event.venue, 'Conference Room')
        self.assertEqual(event.event_type, 'internal')
        self.assertTrue(event.is_upcoming)

    def test_rsvp_functionality(self):
        """Test RSVP functionality"""
        event = Event.objects.create(
            title='Test Event',
            description='Test',
            date=date.today() + timedelta(days=7),
            time=time(14, 30),
            venue='Conference Room',
            created_by=self.user
        )
        
        user2 = User.objects.create_user(username='user2')
        user3 = User.objects.create_user(username='user3')
        
        # Add RSVP responses
        event.rsvp_yes.add(self.user)
        event.rsvp_no.add(user2)
        event.rsvp_maybe.add(user3)
        
        self.assertEqual(event.total_rsvp_yes, 1)
        self.assertEqual(event.total_rsvp_no, 1)
        self.assertEqual(event.total_rsvp_maybe, 1)
        self.assertEqual(event.total_rsvp, 3)
        
        # Test user RSVP status
        self.assertEqual(event.get_user_rsvp_status(self.user), 'yes')
        self.assertEqual(event.get_user_rsvp_status(user2), 'no')
        self.assertEqual(event.get_user_rsvp_status(user3), 'maybe')


class BroadcastAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )

    def test_broadcast_list_requires_authentication(self):
        """Test that broadcast list requires authentication"""
        response = self.client.get('/api/broadcasts/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_broadcast_list_authenticated(self):
        """Test broadcast list for authenticated user"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/broadcasts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_broadcast_creation(self):
        """Test broadcast creation via API"""
        self.client.force_authenticate(user=self.admin)
        
        data = {
            'title': 'API Test Broadcast',
            'description': 'Created via API',
            'priority': 'normal',
            'start_date': timezone.now().isoformat(),
            'end_date': (timezone.now() + timedelta(hours=24)).isoformat(),
            'audience_type': 'all',
            'send_email': False
        }
        
        response = self.client.post('/api/broadcasts/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Broadcast.objects.count(), 1)

    def test_broadcast_acknowledgment(self):
        """Test broadcast acknowledgment via API"""
        broadcast = Broadcast.objects.create(
            title='Test Broadcast',
            description='Test',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(hours=24),
            audience_type='all',
            is_published=True,
            created_by=self.admin
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Acknowledge broadcast
        response = self.client.post(
            f'/api/broadcasts/{broadcast.id}/acknowledge/',
            {'acknowledged': True},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        broadcast.refresh_from_db()
        self.assertTrue(broadcast.acknowledged_by.filter(id=self.user.id).exists())


class EventAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )

    def test_event_creation(self):
        """Test event creation via API"""
        self.client.force_authenticate(user=self.admin)
        
        data = {
            'title': 'API Test Event',
            'description': 'Created via API',
            'date': (date.today() + timedelta(days=7)).isoformat(),
            'time': '14:30:00',
            'venue': 'API Conference Room',
            'event_type': 'internal',
            'is_public': True
        }
        
        response = self.client.post('/api/events/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.count(), 1)

    def test_event_rsvp(self):
        """Test event RSVP via API"""
        event = Event.objects.create(
            title='Test Event',
            description='Test',
            date=date.today() + timedelta(days=7),
            time=time(14, 30),
            venue='Conference Room',
            is_public=True,
            created_by=self.admin
        )
        
        self.client.force_authenticate(user=self.user)
        
        # RSVP to event
        response = self.client.post(
            f'/api/events/{event.id}/rsvp/',
            {'status': 'yes'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertTrue(event.rsvp_yes.filter(id=self.user.id).exists())

    def test_upcoming_events(self):
        """Test upcoming events endpoint"""
        # Create past and future events
        Event.objects.create(
            title='Past Event',
            description='Past',
            date=date.today() - timedelta(days=1),
            time=time(14, 30),
            venue='Past Venue',
            is_public=True,
            created_by=self.admin
        )
        
        Event.objects.create(
            title='Future Event',
            description='Future',
            date=date.today() + timedelta(days=7),
            time=time(14, 30),
            venue='Future Venue',
            is_public=True,
            created_by=self.admin
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/events/upcoming/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Only future event
        self.assertEqual(response.data['results'][0]['title'], 'Future Event')


class GroupModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_group_creation(self):
        """Test group model creation"""
        group = Group.objects.create(
            name='Test Group',
            description='This is a test group',
            group_type='public',
            department='Engineering',
            created_by=self.user
        )
        
        self.assertEqual(group.name, 'Test Group')
        self.assertEqual(group.group_type, 'public')
        self.assertEqual(group.department, 'Engineering')
        self.assertEqual(group.created_by, self.user)

    def test_group_members(self):
        """Test group membership functionality"""
        group = Group.objects.create(
            name='Test Group',
            created_by=self.user
        )
        
        user2 = User.objects.create_user(username='user2')
        user3 = User.objects.create_user(username='user3')
        
        # Add members
        group.members.add(self.user, user2, user3)
        group.owners.add(self.user)
        
        self.assertEqual(group.members.count(), 3)
        self.assertEqual(group.owners.count(), 1)
        self.assertTrue(group.members.filter(id=self.user.id).exists())
        self.assertTrue(group.owners.filter(id=self.user.id).exists())


class MediaModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_media_creation(self):
        """Test media model creation (without actual file)"""
        # Note: This test doesn't upload actual files
        media = Media.objects.create(
            file_name='test.jpg',
            file_type='image',
            file_size=1024,
            uploaded_by=self.user
        )
        
        self.assertEqual(media.file_name, 'test.jpg')
        self.assertEqual(media.file_type, 'image')
        self.assertEqual(media.file_size, 1024)
        self.assertEqual(media.uploaded_by, self.user)


class IntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )

    def test_broadcast_to_group_workflow(self):
        """Test complete workflow: create group, add members, broadcast to group"""
        self.client.force_authenticate(user=self.admin)
        
        # 1. Create a group
        group_data = {
            'name': 'Engineering Team',
            'description': 'Engineering department group',
            'group_type': 'public',
            'department': 'Engineering'
        }
        
        response = self.client.post('/api/groups/', group_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        group_id = response.data['id']
        
        # 2. Add members to group (through admin interface or API)
        group = Group.objects.get(id=group_id)
        group.members.add(self.user1, self.user2)
        
        # 3. Create broadcast targeting the group
        broadcast_data = {
            'title': 'Engineering Announcement',
            'description': 'Important update for engineering team',
            'priority': 'important',
            'start_date': timezone.now().isoformat(),
            'end_date': (timezone.now() + timedelta(hours=24)).isoformat(),
            'audience_type': 'groups',
            'target_group_ids': [group_id],
            'send_email': False
        }
        
        response = self.client.post('/api/broadcasts/', broadcast_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        broadcast_id = response.data['id']
        
        # 4. Verify group members can see the broadcast
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/broadcasts/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        broadcast_titles = [b['title'] for b in response.data['results']]
        self.assertIn('Engineering Announcement', broadcast_titles)
        
        # 5. Test acknowledgment
        response = self.client.post(
            f'/api/broadcasts/{broadcast_id}/acknowledge/',
            {'acknowledged': True},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_event_rsvp_workflow(self):
        """Test complete event workflow: create event, users RSVP, check analytics"""
        self.client.force_authenticate(user=self.admin)
        
        # 1. Create an event
        event_data = {
            'title': 'Team Building Event',
            'description': 'Fun team building activities',
            'date': (date.today() + timedelta(days=14)).isoformat(),
            'time': '10:00:00',
            'venue': 'Company Auditorium',
            'event_type': 'internal',
            'is_public': True,
            'is_important': True
        }
        
        response = self.client.post('/api/events/', event_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event_id = response.data['id']
        
        # 2. User1 RSVPs Yes
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(
            f'/api/events/{event_id}/rsvp/',
            {'status': 'yes'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. User2 RSVPs Maybe
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(
            f'/api/events/{event_id}/rsvp/',
            {'status': 'maybe'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Check analytics (admin only)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/events/{event_id}/analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_rsvp_yes'], 1)
        self.assertEqual(response.data['total_rsvp_maybe'], 1)
        self.assertEqual(response.data['total_rsvp'], 2)
        
        # 5. Check RSVP list
        response = self.client.get(f'/api/events/{event_id}/rsvp_list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['yes']), 1)
        self.assertEqual(len(response.data['maybe']), 1)
        self.assertEqual(len(response.data['no']), 0)

    def test_permissions_workflow(self):
        """Test permission system works correctly"""
        self.client.force_authenticate(user=self.admin)
        
        # 1. Admin creates private group
        group = Group.objects.create(
            name='Private Group',
            group_type='private',
            created_by=self.admin
        )
        group.members.add(self.user1)  # Only user1 is member
        
        # 2. Admin creates broadcast for private group
        broadcast = Broadcast.objects.create(
            title='Private Announcement',
            description='Only for private group members',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(hours=24),
            audience_type='groups',
            is_published=True,
            created_by=self.admin
        )
        broadcast.target_groups.add(group)
        
        # 3. User1 (group member) should see the broadcast
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/broadcasts/')
        
        broadcast_titles = [b['title'] for b in response.data['results']]
        self.assertIn('Private Announcement', broadcast_titles)
        
        # 4. User2 (not a group member) should NOT see the broadcast
        self.client.force_authenticate(user=self.user2)
        response = self.client.get('/api/broadcasts/')
        
        broadcast_titles = [b['title'] for b in response.data['results']]
        self.assertNotIn('Private Announcement', broadcast_titles)