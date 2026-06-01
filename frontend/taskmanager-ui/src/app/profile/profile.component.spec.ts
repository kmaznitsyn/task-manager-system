import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { KeycloakService } from 'keycloak-angular';

import { environment } from '../../environments/environment';
import { ProfileComponent } from './profile.component';

describe('ProfileComponent', () => {
  let component: ProfileComponent;
  let fixture: ComponentFixture<ProfileComponent>;
  let httpMock: HttpTestingController;

  const keycloakStub = {
    getKeycloakInstance: () => ({
      tokenParsed: { email: 'ada@example.com' },
    }),
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProfileComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: KeycloakService, useValue: keycloakStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ProfileComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => httpMock.verify());

  it('should create and load the profile', () => {
    const req = httpMock.expectOne(`${environment.api.userService}/me`);
    expect(req.request.method).toBe('GET');
    req.flush({
      id: '1',
      keycloak_sub: 'sub-1',
      email: 'ada@example.com',
      display_name: 'Ada Lovelace',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    });

    expect(component).toBeTruthy();
    expect(component.state()).toBe('loaded');
    expect(component.initials()).toBe('AL');
  });
});
