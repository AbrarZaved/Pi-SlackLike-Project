"""
Management command to seed permissions and roles into the database.

Usage:
    python manage.py seed_permissions
    
This command will:
1. Create all default permissions organized by category
2. Create default roles (Customer, Business User, Team Member, Admin)
3. Assign appropriate permissions to each role
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from authentication.models import Permission, Role, RolePermission


class Command(BaseCommand):
    help = 'Seed permissions and roles into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all existing roles and permissions before seeding',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        reset = options.get('reset', False)
        
        if reset:
            self.stdout.write(self.style.WARNING('Resetting all permissions and roles...'))
            with transaction.atomic():
                RolePermission.objects.all().delete()
                Role.objects.all().delete()
                Permission.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Reset complete'))
        
        self.stdout.write(self.style.MIGRATE_HEADING('Starting permission and role seeding...'))
        
        with transaction.atomic():
            # Step 1: Create permissions
            permissions_created = self._create_permissions()
            
            # Step 2: Create roles
            roles_created = self._create_roles()
            
            # Step 3: Assign permissions to roles
            assignments_created = self._assign_permissions_to_roles()
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('SEEDING COMPLETE'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'Permissions created: {permissions_created}')
        self.stdout.write(f'Roles created: {roles_created}')
        self.stdout.write(f'Permission assignments: {assignments_created}')
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))

    def _create_permissions(self):
        """Create all default permissions."""
        self.stdout.write(self.style.HTTP_INFO('\n1. Creating Permissions...'))
        
        permissions_data = [
            # User Management
            {
                'codename': 'manage_users',
                'name': 'Manage Users',
                'category': 'user_management',
                'description': 'Create, update, delete users and manage user accounts'
            },
            {
                'codename': 'manage_contacts',
                'name': 'Manage Contacts',
                'category': 'user_management',
                'description': 'View and manage contact lists'
            },
            
            # Communication
            {
                'codename': 'send_receive_messages',
                'name': 'Send & Receive Messages',
                'category': 'communication',
                'description': 'Send and receive direct messages and channel messages'
            },
            {
                'codename': 'calling',
                'name': 'Voice & Video Calling',
                'category': 'communication',
                'description': 'Make and receive voice and video calls'
            },
            
            # Channels
            {
                'codename': 'create_channels',
                'name': 'Create Channels',
                'category': 'channels',
                'description': 'Create new channels and manage channel settings'
            },
            {
                'codename': 'join_channels',
                'name': 'Join Channels',
                'category': 'channels',
                'description': 'Join existing channels and participate in discussions'
            },
            
            # Files
            {
                'codename': 'upload_files',
                'name': 'Upload Files',
                'category': 'files',
                'description': 'Upload files and attachments to messages or channels'
            },
            {
                'codename': 'share_files',
                'name': 'Share Files',
                'category': 'files',
                'description': 'Share files with other users or channels'
            },
            
            # Notifications
            {
                'codename': 'manage_notifications',
                'name': 'Manage Notifications',
                'category': 'notifications',
                'description': 'Configure and manage notification preferences'
            },
        ]
        
        created_count = 0
        for perm_data in permissions_data:
            permission, created = Permission.objects.get_or_create(
                codename=perm_data['codename'],
                defaults={
                    'name': perm_data['name'],
                    'category': perm_data['category'],
                    'description': perm_data['description']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {permission.codename} ({permission.get_category_display()})')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'  - Already exists: {permission.codename}')
                )
        
        return created_count

    def _create_roles(self):
        """Create default roles."""
        self.stdout.write(self.style.HTTP_INFO('\n2. Creating Roles...'))
        
        roles_data = [
            {
                'name': 'Customer',
                'slug': 'customer',
                'description': 'Basic customer role with limited permissions',
                'is_system_role': True
            },
            {
                'name': 'Business User',
                'slug': 'business_user',
                'description': 'Business user with extended communication capabilities',
                'is_system_role': True
            },
            {
                'name': 'Team Member',
                'slug': 'team_member',
                'description': 'Internal team member with channel and file management',
                'is_system_role': True
            },
            {
                'name': 'Admin',
                'slug': 'admin',
                'description': 'Administrator with full system access',
                'is_system_role': True
            },
        ]
        
        created_count = 0
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                slug=role_data['slug'],
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description'],
                    'is_system_role': role_data['is_system_role']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created role: {role.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'  - Already exists: {role.name}')
                )
        
        return created_count

    def _assign_permissions_to_roles(self):
        """Assign permissions to roles based on role definitions."""
        self.stdout.write(self.style.HTTP_INFO('\n3. Assigning Permissions to Roles...'))
        
        # Define role-permission mappings
        role_permissions = {
            'customer': [
                'send_receive_messages',
                'join_channels',
                'manage_notifications',
            ],
            'business_user': [
                'send_receive_messages',
                'calling',
                'join_channels',
                'upload_files',
                'share_files',
                'manage_contacts',
                'manage_notifications',
            ],
            'team_member': [
                'send_receive_messages',
                'calling',
                'create_channels',
                'join_channels',
                'upload_files',
                'share_files',
                'manage_contacts',
                'manage_notifications',
            ],
            'admin': [
                'manage_users',
                'manage_contacts',
                'send_receive_messages',
                'calling',
                'create_channels',
                'join_channels',
                'upload_files',
                'share_files',
                'manage_notifications',
            ],
        }
        
        total_assignments = 0
        
        for role_slug, permission_codenames in role_permissions.items():
            try:
                role = Role.objects.get(slug=role_slug)
                self.stdout.write(f'\n  Assigning permissions to: {role.name}')
                
                role_assignment_count = 0
                for codename in permission_codenames:
                    try:
                        permission = Permission.objects.get(codename=codename)
                        role_permission, created = RolePermission.objects.get_or_create(
                            role=role,
                            permission=permission
                        )
                        if created:
                            role_assignment_count += 1
                            total_assignments += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'    ✓ {codename}')
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(f'    - {codename} (already assigned)')
                            )
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'    ✗ Permission not found: {codename}')
                        )
                
                self.stdout.write(
                    self.style.SUCCESS(f'  Total for {role.name}: {role_assignment_count} permissions')
                )
                
            except Role.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Role not found: {role_slug}')
                )
        
        return total_assignments

    def _print_summary(self):
        """Print a summary of all roles and their permissions."""
        self.stdout.write(self.style.MIGRATE_HEADING('\nROLE PERMISSIONS SUMMARY'))
        self.stdout.write('='*60)
        
        roles = Role.objects.all().prefetch_related('permissions')
        for role in roles:
            self.stdout.write(f'\n{role.name} ({role.permissions.count()} permissions):')
            permissions = role.permissions.all().order_by('category', 'codename')
            
            current_category = None
            for perm in permissions:
                if current_category != perm.category:
                    current_category = perm.category
                    self.stdout.write(f'  [{perm.get_category_display()}]')
                self.stdout.write(f'    • {perm.codename}')
        
        self.stdout.write('\n' + '='*60)
