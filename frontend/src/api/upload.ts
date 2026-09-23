import { apiPostForm } from './client';
import type { UploadResponse } from '@/types/api';

export const uploadApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiPostForm<UploadResponse>('/upload', formData);
  },
};
