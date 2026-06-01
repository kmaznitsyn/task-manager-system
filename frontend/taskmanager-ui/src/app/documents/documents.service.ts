import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { DocumentInput, LogisticsDocument } from './document.model';

@Injectable({ providedIn: 'root' })
export class DocumentsService {
  private http = inject(HttpClient);
  private base = environment.api.docsService;

  list(): Observable<LogisticsDocument[]> {
    return this.http.get<LogisticsDocument[]>(`${this.base}/documents`);
  }

  get(id: string): Observable<LogisticsDocument> {
    return this.http.get<LogisticsDocument>(`${this.base}/documents/${id}`);
  }

  create(input: DocumentInput): Observable<LogisticsDocument> {
    return this.http.post<LogisticsDocument>(`${this.base}/documents`, input);
  }

  process(id: string): Observable<LogisticsDocument> {
    return this.http.post<LogisticsDocument>(
      `${this.base}/documents/${id}/process`,
      {},
    );
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/documents/${id}`);
  }
}
