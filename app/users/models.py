from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    def is_owner(self, project):
        return project.user == self

    def has_edit_rights(self, project):
        return (project.user.email == self.email) or (
            project.viewers.filter(user__email=self.email, share_rights="edit").exists()
        )

    def has_read_rights(self, project):
        return (project.user.email == self.email) or (
            project.viewers.filter(user__email=self.email).exists()
        )
