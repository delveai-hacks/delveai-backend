from ..utils import db


class User(db.Model):
    __tablename__ = "userdata"
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    fullname = db.Column(db.String(), unique=True, nullable=False)
    email = db.Column(db.String(), unique=True, nullable=False)
    password = db.Column(db.String(), unique=True, nullable=False)
    code = db.Column(db.String(), unique=True, nullable=False)

    def __repr__(self):
        return f"User('{self.id}')"

    def save(self):
        db.session.add(self)
        db.session.commit()
