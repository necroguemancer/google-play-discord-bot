import json, os


class Permissions:

    permission_store = {}    
    admin_perm = 'admin'
    def __init__(self, default_admin):
        self.permissions_file_location = "{}{}".format(os.environ['PERMISSIONS_FILE_DIR'], os.environ['PERMISSIONS_FILE_NAME'])

    @property
    def permissions(self):
        if self.permission_store is None or len(self.permission_store.keys()) == 0:
            self.load_permissions()
        else:
            return self.permission_store

    def save_permissions(self):
        with open(self.permissions_file_location, 'w') as perms:
            perms.write(json.dumps(self.permissions, indent=4))

    def load_permissions(self):
        with open(self.permissions_file_location, 'r') as perms:
            self.permission_store = json.loads(perms.read())

    def check_permission(self, perm, user):
        return user in self.permissions.get(perm, [])

    def grant_permission(self, perm, granting_user, requesting_user):
        if self.check_permission(self.admin_perm, granting_user):
            if len(self.permissions.get(perm, [])) == 0:
                self.permissions[perm] = [requesting_user]
            else:
                self.permissions[perm].append(requesting_user)
            self.save_permissions()
        else:
            raise PermissionError("You do not have the required permissions to do that.")

    def remove_permission(self, perm, granting_user, requesting_user):
        if self.check_permission(self.admin_perm, granting_user):
            if len(self.permissions.get(perm, [])) > 1:
                self.permissions[perm].remove(requesting_user)
            else:
                del self.permissions[perm]
            self.save_permissions()
        else:
            raise PermissionError("You do not have the required permissions to do that.")